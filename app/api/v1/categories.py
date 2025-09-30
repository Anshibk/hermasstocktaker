from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, exists, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permission
from app.models.category import CategoryGroup, SubCategory
from app.models.entry import Entry
from app.models.item import Item
from app.schemas.category import (
    CategoryGroupCreate,
    CategoryGroupOut,
    SubCategoryCreate,
    SubCategoryOut,
    SubCategoryUpdate,
)
from app.core.constants import CORE_INVENTORY_GROUPS, CORE_INVENTORY_GROUPS_SET

router = APIRouter(prefix="/categories", tags=["categories"])


def _normalize_subcategory_name(name: str | None) -> str:
    normalized = (name or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sub-category name is required",
        )
    return normalized


def _subcategory_exists(
    db: Session,
    *,
    group_id: uuid.UUID,
    name: str,
    exclude_id: uuid.UUID | None = None,
) -> bool:
    conditions = [
        SubCategory.group_id == group_id,
        func.lower(SubCategory.name) == name.lower(),
    ]
    if exclude_id:
        conditions.append(SubCategory.id != exclude_id)
    return (
        db.query(exists().where(and_(*conditions)))
        .scalar()
    )


@router.get(
    "/groups",
    response_model=list[CategoryGroupOut],
    dependencies=[Depends(get_current_user)],
)
def list_groups(db: Session = Depends(get_db)):
    query = db.query(CategoryGroup).filter(
        CategoryGroup.name.in_(list(CORE_INVENTORY_GROUPS_SET))
    )
    groups = query.all()
    order_index = {name: idx for idx, name in enumerate(CORE_INVENTORY_GROUPS)}
    # preserve a predictable order for the UI based on the official group list
    return sorted(groups, key=lambda group: order_index.get(group.name, len(order_index)))


@router.post(
    "/groups",
    response_model=CategoryGroupOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("can_edit_manage_data"))],
)
def create_group(payload: CategoryGroupCreate, db: Session = Depends(get_db)):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Inventory groups are managed centrally and cannot be created via the UI.",
    )


@router.get(
    "/subs",
    response_model=list[SubCategoryOut],
    dependencies=[Depends(get_current_user)],
)
def list_subcategories(group_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    query = db.query(SubCategory)
    if group_id:
        query = query.filter(SubCategory.group_id == group_id)
    return query.order_by(SubCategory.name).all()


@router.post("/subs", response_model=SubCategoryOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("can_edit_manage_data"))])
def create_subcategory(payload: SubCategoryCreate, db: Session = Depends(get_db)):
    if payload.group_id:
        group = db.get(CategoryGroup, payload.group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group not found")
        if group.name not in CORE_INVENTORY_GROUPS_SET:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sub-categories can only be attached to official inventory groups.",
            )
    name = _normalize_subcategory_name(payload.name)
    if _subcategory_exists(db, group_id=payload.group_id, name=name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sub-category name already exists in this group",
        )
    data = payload.dict()
    data["name"] = name
    sub = SubCategory(**data)
    db.add(sub)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sub-category name already exists in this group",
        ) from exc
    db.refresh(sub)
    return sub


@router.put("/subs/{sub_id}", response_model=SubCategoryOut, dependencies=[Depends(require_permission("can_edit_manage_data"))])
def update_subcategory(sub_id: uuid.UUID, payload: SubCategoryUpdate, db: Session = Depends(get_db)):
    sub = db.get(SubCategory, sub_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category not found")
    data = payload.dict(exclude_unset=True)
    if "group_id" in data and data["group_id"] != sub.group_id:
        group = db.get(CategoryGroup, data["group_id"])
        if not group:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group not found")
        if group.name not in CORE_INVENTORY_GROUPS_SET:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sub-categories can only be attached to official inventory groups.",
            )
    target_group_id = data.get("group_id", sub.group_id)
    if "name" in data:
        data["name"] = _normalize_subcategory_name(data["name"])
    candidate_name = data.get("name", sub.name)
    if _subcategory_exists(
        db,
        group_id=target_group_id,
        name=candidate_name,
        exclude_id=sub_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sub-category name already exists in this group",
        )

    for key, value in data.items():
        setattr(sub, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sub-category name already exists in this group",
        ) from exc
    db.refresh(sub)
    return sub


@router.delete("/subs/{sub_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("can_edit_manage_data"))])
def delete_subcategory(sub_id: uuid.UUID, db: Session = Depends(get_db)):
    sub = db.get(SubCategory, sub_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category not found")
    has_items = db.query(exists().where(Item.category_id == sub_id)).scalar()
    if has_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a sub-category that is linked to items.",
        )
    has_entries = db.query(exists().where(Entry.category_id == sub_id)).scalar()
    if has_entries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a sub-category that has inventory entries.",
        )
    db.delete(sub)
    db.commit()
    return None
