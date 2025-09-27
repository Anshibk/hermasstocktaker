from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.role import RoleOut


class UserBase(BaseModel):
    name: str
    username: str
    is_active: bool = True
    dashboard_share_enabled: bool = False


class UserCreate(UserBase):
    password: str
    role_id: uuid.UUID


class UserUpdate(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    role_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None
    dashboard_share_enabled: Optional[bool] = None


class UserOut(UserBase):
    id: uuid.UUID
    role: RoleOut
    parent_admin_id: Optional[uuid.UUID]

    model_config = ConfigDict(from_attributes=True)
