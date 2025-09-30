from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import requests
from fastapi import HTTPException, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.role import Role
from app.models.user import User


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
STATE_SESSION_KEY = "google_oauth_state"
STATE_TTL_SECONDS = 600


def _require_oauth_configuration() -> None:
    if not settings.google_client_id or not settings.google_client_secret or not settings.google_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured",
        )


def _store_state(session: dict[str, Any], state: dict[str, Any]) -> str:
    nonce = secrets.token_urlsafe(32)
    state_copy = {"nonce": nonce, "issued_at": int(time.time())}
    state_copy.update({k: v for k, v in state.items() if v is not None})
    session[STATE_SESSION_KEY] = state_copy
    return nonce


def build_google_oauth_redirect(request: Request, invitation_token: str | None, next_url: str | None) -> str:
    _require_oauth_configuration()
    invitation_token = (invitation_token or "").strip() or None
    if next_url and not next_url.startswith("/"):
        next_url = "/dashboard"
    nonce = _store_state(
        request.session,
        {"invitation_token": invitation_token, "next_url": next_url or "/dashboard"},
    )
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "select_account",
            "state": nonce,
        }
    )
    return f"{GOOGLE_AUTH_URL}?{query}"


def _exchange_code_for_tokens(code: str) -> dict[str, Any]:
    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
    except requests.RequestException as exc:  # pragma: no cover - network failure path
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to reach Google") from exc
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google login failed")
    data = response.json()
    if "id_token" not in data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google login did not return an id token")
    return data


def _verify_id_token(raw_token: str) -> dict[str, Any]:
    try:
        return id_token.verify_oauth2_token(
            raw_token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:  # pragma: no cover - library raises for invalid tokens
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token") from exc


def _ensure_allowed_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized.endswith(f"@{settings.google_allowed_domain}"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Gmail accounts are allowed")
    return normalized


def _ensure_superuser(db: Session, email: str, google_sub: str, full_name: str | None) -> User:
    admin_role = (
        db.query(Role)
        .filter(func.lower(Role.name) == "admin")
        .one_or_none()
    )
    if not admin_role:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Admin role not configured")
    user = (
        db.query(User)
        .filter(func.lower(User.email) == email)
        .one_or_none()
    )
    if not user:
        user = User(
            name=full_name or email.split("@")[0],
            username=email,
            email=email,
            google_sub=google_sub,
            password=None,
            role_id=admin_role.id,
            parent_admin_id=None,
            dashboard_share_enabled=True,
            is_active=True,
        )
        db.add(user)
    else:
        user.name = full_name or user.name or email.split("@")[0]
        user.email = email
        user.username = email
        user.google_sub = google_sub
        user.role_id = admin_role.id
        user.is_active = True
    user.invitation_token = None
    user.invited_at = datetime.now(tz=UTC)
    db.commit()
    db.refresh(user)
    return user


def _link_existing_user(user: User, email: str, google_sub: str, full_name: str | None) -> None:
    if user.google_sub and user.google_sub != google_sub:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Google account mismatch")
    user.google_sub = google_sub
    user.email = email
    user.username = user.username or email
    if full_name and not user.name:
        user.name = full_name


def _apply_invitation(user: User, invitation_token: str | None) -> None:
    if invitation_token and user.invitation_token == invitation_token:
        user.invitation_token = None
        user.invited_at = datetime.now(tz=UTC)


def _resolve_user(
    db: Session,
    email: str,
    google_sub: str,
    full_name: str | None,
    invitation_token: str | None,
) -> User:
    user = db.query(User).filter(User.google_sub == google_sub).one_or_none()
    if not user:
        user = (
            db.query(User)
            .filter(func.lower(User.email) == email)
            .one_or_none()
        )
    if user:
        if user.invitation_token and not invitation_token and not user.google_sub:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="An invitation code is required for first sign-in")
        _link_existing_user(user, email, google_sub, full_name)
        _apply_invitation(user, invitation_token)
        db.commit()
        db.refresh(user)
        return user

    if invitation_token:
        invited_user = (
            db.query(User)
            .filter(User.invitation_token == invitation_token)
            .one_or_none()
        )
        if not invited_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invitation not found")
        if invited_user.email and invited_user.email != email:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invitation email mismatch")
        _link_existing_user(invited_user, email, google_sub, full_name)
        _apply_invitation(invited_user, invitation_token)
        if not invited_user.name:
            invited_user.name = full_name or email.split("@")[0]
        db.commit()
        db.refresh(invited_user)
        return invited_user

    if email == settings.google_superuser_email and email:
        return _ensure_superuser(db, email, google_sub, full_name)

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not invited to this account")


def complete_google_oauth(db: Session, request: Request, code: str, state_token: str | None) -> str:
    _require_oauth_configuration()
    session_state = request.session.get(STATE_SESSION_KEY)
    if not session_state or not state_token or session_state.get("nonce") != state_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid login state")
    issued_at = int(session_state.get("issued_at", 0))
    if int(time.time()) - issued_at > STATE_TTL_SECONDS:
        request.session.pop(STATE_SESSION_KEY, None)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login session expired")

    invitation_token = session_state.get("invitation_token")
    next_url = session_state.get("next_url") or "/dashboard"
    request.session.pop(STATE_SESSION_KEY, None)

    token_data = _exchange_code_for_tokens(code)
    payload = _verify_id_token(token_data["id_token"])

    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google account has no email")
    if not payload.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Google email is not verified")
    email = _ensure_allowed_email(email)

    google_sub = payload.get("sub")
    if not google_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google response missing subject")

    full_name = payload.get("name")
    user = _resolve_user(db, email, google_sub, full_name, invitation_token)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    request.session["user_id"] = str(user.id)
    request.session["role_id"] = str(user.role_id)
    return next_url or "/dashboard"
