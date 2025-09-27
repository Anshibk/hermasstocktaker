from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    ok: bool
