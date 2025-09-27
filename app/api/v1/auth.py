from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.schemas.auth import AuthResponse, LoginRequest
from app.services import auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = auth_service.login(db, payload)
    request.session["user_id"] = str(user.id)
    request.session["role_id"] = str(user.role_id)
    return AuthResponse(ok=True)


@router.post("/logout", response_model=AuthResponse)
def logout(request: Request):
    request.session.clear()
    return AuthResponse(ok=True)
