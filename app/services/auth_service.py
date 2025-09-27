from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from loginpage import authenticate

from app.schemas.auth import LoginRequest


def login(db: Session, payload: LoginRequest):
    user = authenticate(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user
