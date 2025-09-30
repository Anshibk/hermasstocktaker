from __future__ import annotations

import uuid
from secrets import token_urlsafe
from typing import Final

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_permission
from loginpage import hash_password

from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate


PROTECTED_USERNAMES: Final = {"admin", "adminthegreat"}


def _is_protected_user(user: User | None) -> bool:
    if not user or not user.username:
        return False
    username = user.username.strip().casefold()
    protected = {name.casefold() for name in PROTECTED_USERNAMES}
    superuser_email = settings.google_superuser_email.strip().casefold() if settings.google_superuser_email else ""
    if superuser_email:
        protected.add(superuser_email)
    return username in protected


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
    username_raw = (payload.username or "").strip()
    if not username_raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")
    if "@" not in username_raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A Gmail address is required")
    username = username_raw.casefold()
    domain = username.split("@", 1)[1]
    if domain not in {"gmail.com", "googlemail.com"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only Gmail accounts can be invited")

    if (
        db.query(User)
        .filter(func.lower(User.username) == username)
        .first()
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    display_name = (payload.name or "").strip()
    hashed_secret = hash_password(token_urlsafe(32))
    user = User(
        username=username,
        name=display_name or username_raw,
        password=hashed_secret,
        role_id=payload.role_id,
        is_active=payload.is_active,
        dashboard_share_enabled=payload.dashboard_share_enabled,
        google_sub=None,
        parent_admin_id=current_user.id if current_user.parent_admin_id is None else current_user.parent_admin_id,
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
        illegal_fields = [key for key in data.keys() if key not in {"name", "reset_google_link"}]
        if illegal_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The primary administrator cannot change those fields.",
            )

    updates: dict[str, object] = {}
    if "name" in data:
        name = (data["name"] or "").strip()
        updates["name"] = name if name else user.username

    for key in ("role_id", "is_active", "dashboard_share_enabled"):
        if key in data and key not in updates:
            updates[key] = data[key]

    for key, value in updates.items():
        setattr(user, key, value)

    if data.get("reset_google_link"):
        user.google_sub = None

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
