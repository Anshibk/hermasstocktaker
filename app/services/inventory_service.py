from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy.orm import Session, selectinload

from app.core.realtime import notify_entry_created, notify_entry_deleted, notify_entry_updated
from app.models.entry import Entry, EntryType
from app.schemas.entry import EntryCreate, EntryUpdate


def _combine_entry_datetime(entry_date: date | None, existing: datetime | None) -> datetime | None:
    if entry_date is None:
        return existing
    base_time = time(0, 0, tzinfo=timezone.utc)
    if isinstance(existing, datetime):
        base_time = existing.timetz()
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=timezone.utc)
    return datetime.combine(entry_date, base_time)


def list_entries(db: Session, *, user_ids: list[uuid.UUID] | None = None, entry_type: EntryType | None = None) -> list[Entry]:
    query = db.query(Entry).options(selectinload(Entry.user))
    if user_ids is not None:
        query = query.filter(Entry.user_id.in_(user_ids))
    if entry_type:
        query = query.filter(Entry.type == entry_type)
    return query.order_by(Entry.created_at.desc()).all()


def create_entry(db: Session, payload: EntryCreate, user_id: uuid.UUID) -> Entry:
    data = payload.dict()
    entry_date = data.pop("entry_date", None)
    entry = Entry(**data, user_id=user_id)
    combined = _combine_entry_datetime(entry_date, entry.created_at)
    if combined is not None:
        entry.created_at = combined
    db.add(entry)
    db.commit()
    db.refresh(entry)
    try:
        db.refresh(entry, attribute_names=["user"])
    except Exception:  # noqa: BLE001
        _ = getattr(entry, 'user', None)
    notify_entry_created(entry)
    return entry


def update_entry(db: Session, entry_id: uuid.UUID, payload: EntryUpdate) -> Entry:
    entry = db.get(Entry, entry_id)
    if not entry:
        raise ValueError("Entry not found")
    data = payload.dict(exclude_unset=True)
    entry_date = data.pop("entry_date", None)
    for key, value in data.items():
        setattr(entry, key, value)
    combined = _combine_entry_datetime(entry_date, entry.created_at)
    if combined is not None:
        entry.created_at = combined
    db.commit()
    db.refresh(entry)
    try:
        db.refresh(entry, attribute_names=["user"])
    except Exception:  # noqa: BLE001
        _ = getattr(entry, 'user', None)
    notify_entry_updated(entry)
    return entry


def delete_entry(db: Session, entry_id: uuid.UUID) -> None:
    entry = db.get(Entry, entry_id)
    if not entry:
        raise ValueError("Entry not found")
    entry_id = str(entry.id)
    entry_type = str(getattr(entry.type, 'value', entry.type)).lower()
    db.delete(entry)
    db.commit()
    notify_entry_deleted(entry_id, entry_type)
