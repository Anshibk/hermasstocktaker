from __future__ import annotations

from secrets import token_urlsafe
from typing import Any

from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import func
from sqlalchemy.orm import Session

from loginpage import hash_password

from app.core.config import settings
from app.core.deps import ADMIN_ROLE_NAME
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import LoginRequest


GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}


def _get_admin_role(db: Session) -> Role | None:
    return db.query(Role).filter(func.lower(Role.name) == ADMIN_ROLE_NAME).one_or_none()


def _provision_superuser(db: Session, email: str, google_sub: str, profile: dict[str, Any]) -> User:
    admin_role = _get_admin_role(db)
    if not admin_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Administrator role is not configured.",
        )

    display_name = (profile.get("name") or "").strip() or email
    user = User(
        username=email,
        name=display_name,
        password=hash_password(token_urlsafe(32)),
        role_id=admin_role.id,
        is_active=True,
        dashboard_share_enabled=True,
        google_sub=google_sub,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _verify_credential(credential: str) -> dict[str, Any]:
    client_id = settings.google_client_id
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google authentication is not configured.",
        )
    try:
        id_info = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
        )
    except ValueError as exc:  # pragma: no cover - library raises ValueError on invalid token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential.",
        ) from exc

    if id_info.get("iss") not in GOOGLE_ISSUERS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Untrusted Google issuer.",
        )
    if not id_info.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your Google email must be verified.",
        )
    return id_info


def login(db: Session, payload: LoginRequest) -> User:
    credential = (payload.credential or "").strip()
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Google credential.",
        )

    id_info = _verify_credential(credential)
    email_raw = (id_info.get("email") or "").strip()
    email = email_raw.casefold()
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential.",
        )

    domain = email.split("@", 1)[1]
    if domain not in GMAIL_DOMAINS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A Gmail account is required.",
        )

    google_sub = id_info.get("sub")
    if not google_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential.",
        )

    superuser_email = settings.google_superuser_email.strip().casefold() if settings.google_superuser_email else ""

    user = (
        db.query(User)
        .filter(func.lower(User.username) == email)
        .one_or_none()
    )

    if not user:
        if superuser_email and email == superuser_email:
            return _provision_superuser(db, email, google_sub, id_info)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access. Please contact your administrator.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive. Please contact your administrator.",
        )

    if user.google_sub and user.google_sub != google_sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This Google account is not linked to your profile.",
        )

    updated = False
    if not user.google_sub:
        user.google_sub = google_sub
        updated = True

    display_name = (id_info.get("name") or "").strip()
    if display_name and (not user.name or user.name.strip().casefold() == user.username.casefold()):
        user.name = display_name
        updated = True

    if updated:
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
