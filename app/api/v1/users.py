from __future__ import annotations

import secrets
import uuid
from typing import Final

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_permission

from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate


PROTECTED_USERNAMES: Final = {"admin", "adminthegreat"}


def _is_protected_user(user: User | None) -> bool:
    if not user or not user.username:
        return False
    username_protected = user.username.casefold() in PROTECTED_USERNAMES
    email_protected = bool(settings.google_superuser_email) and bool(user.email) and user.email.casefold() == settings.google_superuser_email
    return username_protected or email_protected


router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_permission("can_manage_users"))],
)


@router.get("/", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.username).all()


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")
    if not email.endswith(f"@{settings.google_allowed_domain}"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only Gmail addresses may be invited")
    exists = (
        db.query(User)
        .filter(func.lower(User.email) == email)
        .one_or_none()
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A user with this email already exists")
    username_exists = (
        db.query(User)
        .filter(func.lower(User.username) == email)
        .one_or_none()
    )
    if username_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A user with this email already exists")
    username = email
    invitation_token = secrets.token_urlsafe(32)
    user = User(
        name=(payload.name or "").strip() or email.split("@")[0],
        username=username,
        email=email,
        password=None,
        role_id=payload.role_id,
        parent_admin_id=current_user.id if current_user.parent_admin_id is None else current_user.parent_admin_id,
        dashboard_share_enabled=payload.dashboard_share_enabled,
        is_active=payload.is_active,
        invitation_token=invitation_token,
        invited_at=None,
        invited_by_id=current_user.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, payload: UserUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    is_protected = _is_protected_user(user)
    data = payload.dict(exclude_unset=True)

    if is_protected:
        illegal_fields = [key for key in data.keys() if key not in {"dashboard_share_enabled", "is_active"}]
        if illegal_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The default admin account cannot be modified",
            )

    updates: dict[str, object] = {}
    if "name" in data:
        name = (data["name"] or "").strip()
        if name:
            updates["name"] = name

    for key in ("role_id", "is_active", "dashboard_share_enabled"):
        if key in data:
            updates[key] = data[key]

    if data.get("regenerate_invitation"):
        if user.google_sub:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already linked to Google")
        updates["invitation_token"] = secrets.token_urlsafe(32)
        updates["invited_at"] = None

    for key, value in updates.items():
        setattr(user, key, value)

    if is_protected and not user.is_active:
        user.is_active = True

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete current user")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if _is_protected_user(user):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete default admin")
    db.delete(user)
    db.commit()
    return None
