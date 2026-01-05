from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company, get_db
from app.models.company import Company
from app.models.item import Item


router = APIRouter(prefix="/items", tags=["items"])


# -----------------------------
# Schemas (Pydantic v2)
# -----------------------------
class ItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sku: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = None
    unit_price: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    taxable: bool = False
    active: bool = True


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    sku: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = None
    unit_price: Optional[Decimal] = Field(default=None, ge=Decimal("0.00"))
    taxable: Optional[bool] = None
    active: Optional[bool] = None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    name: str
    sku: Optional[str]
    description: Optional[str]
    unit_price: Decimal
    taxable: bool
    active: bool
    created_at: datetime


# -----------------------------
# Helpers
# -----------------------------
def _get_item_or_404(db: Session, company_id: str, item_id: str) -> Item:
    stmt = select(Item).where(Item.id == item_id, Item.company_id == company_id)
    item = db.execute(stmt).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


# -----------------------------
# Routes
# -----------------------------
@router.get("", response_model=List[ItemOut])
def list_items(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    include_inactive: bool = False,
) -> List[Item]:
    stmt = select(Item).where(Item.company_id == company.id)
    if not include_inactive:
        stmt = stmt.where(Item.active.is_(True))
    stmt = stmt.order_by(Item.created_at.desc())

    return list(db.execute(stmt).scalars().all())


@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: ItemCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
) -> Item:
    item = Item(
        company_id=company.id,
        name=payload.name.strip(),
        sku=(payload.sku.strip() if payload.sku else None),
        description=payload.description,
        unit_price=payload.unit_price,  # Numeric column accepts Decimal cleanly
        taxable=payload.taxable,
        active=payload.active,
    )

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{item_id}", response_model=ItemOut)
def get_item(
    item_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
) -> Item:
    return _get_item_or_404(db, company.id, item_id)


@router.put("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: str,
    payload: ItemUpdate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
) -> Item:
    item = _get_item_or_404(db, company.id, item_id)

    if payload.name is not None:
        item.name = payload.name.strip()
    if payload.sku is not None:
        item.sku = payload.sku.strip() if payload.sku else None
    if payload.description is not None:
        item.description = payload.description
    if payload.unit_price is not None:
        item.unit_price = payload.unit_price
    if payload.taxable is not None:
        item.taxable = payload.taxable
    if payload.active is not None:
        item.active = payload.active

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    item = (
        db.query(Item)
        .filter(Item.id == item_id, Item.company_id == company.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(item)
    db.commit()

    # ? 204 must return no body
    return Response(status_code=status.HTTP_204_NO_CONTENT)