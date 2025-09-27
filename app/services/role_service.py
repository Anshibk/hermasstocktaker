from __future__ import annotations

import uuid
from typing import Final

from sqlalchemy.orm import Session

from app.models.role import DashboardScope, EntryScope, Role
from app.schemas.role import RoleCreate, RoleUpdate


ADMIN_ROLE_NAME: Final = "admin"
_SCOPE_FIELDS: Final = (
    "dashboard_scope",
    "add_item_scope",
    "raw_scope",
    "sfg_scope",
    "fg_scope",
    "entry_scope",
)


class RoleProtectionError(Exception):
    """Raised when a protected role is modified in an unsupported way."""


def _is_admin_role(role: Role | None) -> bool:
    if not role or not role.name:
        return False
    return role.name.casefold() == ADMIN_ROLE_NAME


def _apply_non_admin_broadcast_defaults(role: Role) -> None:
    role.dashboard_scope = DashboardScope.OWN
    role.add_item_scope = DashboardScope.OWN
    role.entry_scope = EntryScope.OWN
    role.raw_scope = EntryScope.OWN
    role.sfg_scope = EntryScope.OWN
    role.fg_scope = EntryScope.OWN
    role.can_edit_add_item = False


def list_roles(db: Session) -> list[Role]:
    return db.query(Role).order_by(Role.name).all()


def create_role(db: Session, payload: RoleCreate) -> Role:
    role = Role(**payload.dict())
    if not _is_admin_role(role):
        _apply_non_admin_broadcast_defaults(role)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def update_role(db: Session, role_id: uuid.UUID, payload: RoleUpdate) -> Role:
    role = db.get(Role, role_id)
    if not role:
        raise ValueError("Role not found")
    data = payload.dict(exclude_unset=True)
    if _is_admin_role(role):
        allowed_for_admin = {
            "dashboard_scope",
            "add_item_scope",
            "raw_scope",
            "sfg_scope",
            "fg_scope",
            "entry_scope",
            "name",
        }
        protected_payload: dict[str, object] = {}
        for field, value in list(data.items()):
            if field in allowed_for_admin:
                if field == "name":
                    if (value or "").casefold() != role.name.casefold():
                        raise RoleProtectionError("Admin role name cannot be changed.")
                    data.pop("name", None)
                else:
                    protected_payload[field] = value
                continue
            current_value = getattr(role, field, None)
            if current_value != value:
                raise RoleProtectionError("Admin role permissions are locked.")
            data.pop(field, None)
            data = protected_payload
    else:
        for field in _SCOPE_FIELDS:
            data.pop(field, None)
    for key, value in data.items():
        setattr(role, key, value)
    if not _is_admin_role(role):
        _apply_non_admin_broadcast_defaults(role)
    db.commit()
    db.refresh(role)
    return role


def delete_role(db: Session, role_id: uuid.UUID) -> None:
    role = db.get(Role, role_id)
    if not role:
        raise ValueError("Role not found")
    if _is_admin_role(role):
        raise RoleProtectionError("Admin role cannot be deleted.")
    if role.users:
        raise ValueError("Cannot delete role with assigned users")
    db.delete(role)
    db.commit()
