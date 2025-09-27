from __future__ import annotations

from collections.abc import Callable, Iterable
import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.entry import EntryType
from app.models.role import DashboardScope, EntryScope, Role
from app.models.user import User


def get_db() -> Iterable[Session]:
    yield from get_session()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = db.get(User, uuid.UUID(str(user_id)))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user


def require_permission(flag: str) -> Callable:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if not getattr(user.role, flag):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user

    return dependency


ADMIN_ROLE_NAME = "admin"


def is_admin_user(user: User) -> bool:
    role_name = getattr(getattr(user, "role", None), "name", "")
    return bool(role_name and role_name.casefold() == ADMIN_ROLE_NAME)


def _get_admin_role(db: Session) -> Role | None:
    return (
        db.query(Role)
        .filter(func.lower(Role.name) == ADMIN_ROLE_NAME)
        .one_or_none()
    )


def _broadcast_enabled(admin_role: Role | None, scope_field: str) -> bool:
    if not admin_role or not hasattr(admin_role, scope_field):
        return False
    scope_value = getattr(admin_role, scope_field)
    if isinstance(scope_value, (DashboardScope, EntryScope)):
        enum_cls = scope_value.__class__
        return scope_value == enum_cls.ORG
    if isinstance(scope_value, str):
        return scope_value.lower() == "org"
    return False


def resolve_dashboard_visible_user_ids(db: Session, user: User) -> set[uuid.UUID] | None:
    """Return user ids visible on dashboard; ``None`` means no restriction."""

    if is_admin_user(user):
        return None

    admin_role = _get_admin_role(db)
    if _broadcast_enabled(admin_role, "dashboard_scope"):
        return None

    return {user.id}


ENTRY_BROADCAST_FIELDS: dict[EntryType | None, str] = {
    EntryType.RAW: "raw_scope",
    EntryType.SFG: "sfg_scope",
    EntryType.FG: "fg_scope",
    None: "entry_scope",
}


def resolve_entry_view_user_ids(
    db: Session,
    user: User,
    entry_type: EntryType | None = None,
) -> set[uuid.UUID] | None:
    """User ids whose entries are visible when listing entries."""

    if is_admin_user(user):
        return None

    scope_field = ENTRY_BROADCAST_FIELDS.get(entry_type, "entry_scope")
    admin_role = _get_admin_role(db)
    if _broadcast_enabled(admin_role, scope_field):
        return None

    return {user.id}


def resolve_entry_edit_user_ids(
    db: Session,
    user: User,
    entry_type: EntryType | None = None,
) -> set[uuid.UUID] | None:
    """User ids whose entries can be edited or deleted by *user*."""

    if is_admin_user(user):
        return None

    return {user.id}
