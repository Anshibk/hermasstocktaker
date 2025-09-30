from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    credential: str


class AuthResponse(BaseModel):
    ok: bool
