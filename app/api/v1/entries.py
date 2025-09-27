from __future__ import annotations

import uuid
import asyncio
from contextlib import suppress
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.deps import (
    get_current_user,
    get_db,
    is_admin_user,
    resolve_entry_edit_user_ids,
    resolve_entry_view_user_ids,
)
from app.models.entry import Entry, EntryType
from app.models.user import User
from app.schemas.entry import EntryCreate, EntryOut, EntryUpdate
from app.services import inventory_service
from app.core.realtime import entry_event_broker

router = APIRouter(prefix="/entries", tags=["entries"])


def _parse_type(value: str | None) -> Optional[EntryType]:
    if value is None:
        return None
    try:
        return EntryType(value.lower())
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid entry type") from exc


def _ensure_permission(user: User, entry_type: EntryType) -> None:
    flag_map = {
        EntryType.RAW: "can_add_entry_raw",
        EntryType.SFG: "can_add_entry_sfg",
        EntryType.FG: "can_add_entry_fg",
    }
    if not getattr(user.role, flag_map[entry_type]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _ensure_bulk_permission(user: User, entry_type: EntryType) -> None:
    flag_map = {
        EntryType.RAW: "can_bulk_edit_delete_raw",
        EntryType.SFG: "can_bulk_edit_delete_sfg",
        EntryType.FG: "can_bulk_edit_delete_fg",
    }
    if not getattr(user.role, flag_map[entry_type]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _ensure_edit_permission(user: User, entry_type: EntryType) -> None:
    flag_map = {
        EntryType.RAW: "can_edit_entry_raw",
        EntryType.SFG: "can_edit_entry_sfg",
        EntryType.FG: "can_edit_entry_fg",
    }
    if not getattr(user.role, flag_map[entry_type]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.get("/", response_model=list[EntryOut])
def list_entries(
    entry_type: str | None = Query(default=None, alias="type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    type_filter = _parse_type(entry_type)
    visible_user_ids = resolve_entry_view_user_ids(db, current_user, type_filter)
    if visible_user_ids is not None and not visible_user_ids:
        return []
    entries = inventory_service.list_entries(
        db,
        user_ids=None if visible_user_ids is None else list(visible_user_ids),
        entry_type=type_filter,
    )
    return entries


@router.post("/", response_model=EntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: EntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_permission(current_user, payload.type)
    return inventory_service.create_entry(db, payload, current_user.id)


@router.put("/{entry_id}", response_model=EntryOut)
def update_entry(entry_id: uuid.UUID, payload: EntryUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    entry = db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    _ensure_edit_permission(current_user, entry.type)
    allowed_user_ids = resolve_entry_edit_user_ids(db, current_user, entry.type)
    if allowed_user_ids is not None and entry.user_id not in allowed_user_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return inventory_service.update_entry(db, entry_id, payload)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    entry = db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    allowed_user_ids = resolve_entry_edit_user_ids(db, current_user, entry.type)
    if allowed_user_ids is not None and entry.user_id not in allowed_user_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    _ensure_bulk_permission(current_user, entry.type)
    inventory_service.delete_entry(db, entry_id)
    return None


@router.websocket("/stream")
async def entry_stream(websocket: WebSocket):
    user_id = websocket.session.get("user_id") if hasattr(websocket, "session") else None
    if not user_id:
        await websocket.close(code=1008)
        return
    try:
        user_uuid = uuid.UUID(str(user_id))
    except ValueError:
        await websocket.close(code=1008)
        return
    with SessionLocal() as db:
        user = db.get(User, user_uuid)
        if not user or not user.is_active or not is_admin_user(user):
            await websocket.close(code=1008)
            return
    await websocket.accept()
    queue = await entry_event_broker.subscribe()
    receiver_task: asyncio.Task[str] | None = None
    try:
        await websocket.send_json({"type": "connected"})
        while True:
            if receiver_task is None:
                receiver_task = asyncio.create_task(websocket.receive_text())
            waiter = asyncio.create_task(queue.get())
            done, pending = await asyncio.wait(
                {waiter, receiver_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if receiver_task in done:
                # client closed connection
                break
            message = waiter.result()
            await websocket.send_json(message)
            waiter.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        await entry_event_broker.unsubscribe(queue)
        if receiver_task:
            receiver_task.cancel()
            with suppress(Exception):
                await receiver_task
