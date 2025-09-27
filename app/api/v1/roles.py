from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission, get_db
from app.schemas.role import RoleCreate, RoleOut, RoleUpdate
from app.services import role_service
from app.services.role_service import RoleProtectionError


router = APIRouter(
    prefix="/roles",
    tags=["roles"],
    dependencies=[Depends(require_permission("can_manage_roles"))],
)


@router.get("/", response_model=list[RoleOut])
def list_roles(db: Session = Depends(get_db)):
    return role_service.list_roles(db)


@router.post("/", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(payload: RoleCreate, db: Session = Depends(get_db)):
    return role_service.create_role(db, payload)


@router.put("/{role_id}", response_model=RoleOut)
def update_role(role_id: uuid.UUID, payload: RoleUpdate, db: Session = Depends(get_db)):
    try:
        return role_service.update_role(db, role_id, payload)
    except RoleProtectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        role_service.delete_role(db, role_id)
    except RoleProtectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return None
