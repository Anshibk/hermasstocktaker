from __future__ import annotations

import uuid
from typing import Final

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permission
from loginpage import hash_password

from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate


PROTECTED_USERNAMES: Final = {"admin", "adminthegreat"}


def _is_protected_user(user: User | None) -> bool:
    if not user or not user.username:
        return False
    return user.username.casefold() in PROTECTED_USERNAMES


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
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is required")
    if db.query(User).filter(User.username.ilike(username)).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    data = payload.dict()
    data["username"] = username
    data["name"] = data.get("name") or data["username"]
    password = data["password"].strip()
    if not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password is required")
    data["password"] = hash_password(password)
    user = User(
        **data,
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
        illegal_fields = [key for key in data.keys() if key != "password"]
        if illegal_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The default admin account can only change its password.",
            )

    updates: dict[str, object] = {}
    if "password" in data:
        password = (data["password"] or "").strip()
        if not password:
            data.pop("password")
        else:
            updates["password"] = hash_password(password)

    if "name" in data:
        name = data["name"] or ""
        updates["name"] = name if name else user.username

    for key in ("role_id", "is_active", "dashboard_share_enabled"):
        if key in data and key not in updates:
            updates[key] = data[key]

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
