from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company
from app.db.session import get_db
from app.models.company import Company
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.item import Item
from app.services.invoice_totals import recalc_invoice_totals

router = APIRouter(prefix="/invoices", tags=["invoices"])

# -----------------------------
# Helpers / rules
# -----------------------------
ALLOWED_STATUSES = {"draft", "sent", "paid", "void"}

# Allowed transitions:
# draft -> sent/void
# sent  -> paid/void
# paid  -> (no changes)
# void  -> (no changes)
ALLOWED_TRANSITIONS = {
    "draft": {"sent", "void"},
    "sent": {"paid", "void"},
    "paid": set(),
    "void": set(),
}


def _ensure_company_invoice(invoice: Invoice, company: Company):
    if invoice.company_id != company.id:
        raise HTTPException(status_code=404, detail="Invoice not found")


def _ensure_editable(invoice: Invoice):
    # Typically you don't allow edits after paid/void
    if invoice.status in ("paid", "void"):
        raise HTTPException(
            status_code=409,
            detail=f"Invoice is {invoice.status} and cannot be edited",
        )


def _get_invoice(db: Session, invoice_id: str) -> Invoice:
    inv = db.execute(select(Invoice).where(Invoice.id == invoice_id)).scalars().first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


def _get_line(db: Session, line_id: str) -> InvoiceLine:
    line = db.execute(select(InvoiceLine).where(InvoiceLine.id == line_id)).scalars().first()
    if not line:
        raise HTTPException(status_code=404, detail="Invoice line not found")
    return line


# -----------------------------
# Schemas
# -----------------------------
class InvoiceCreate(BaseModel):
    customer_id: str
    number: Optional[str] = None
    tax_rate: Decimal = Field(default=Decimal("0.0000"))
    currency: str = Field(default="USD", max_length=10)
    notes: Optional[str] = None


class InvoiceUpdate(BaseModel):
    customer_id: Optional[str] = None
    number: Optional[str] = None
    tax_rate: Optional[Decimal] = None
    currency: Optional[str] = Field(default=None, max_length=10)
    notes: Optional[str] = None


class InvoiceOut(BaseModel):
    id: str
    company_id: str
    customer_id: str
    number: Optional[str]
    tax_rate: Decimal
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    status: str
    currency: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InvoiceLineCreate(BaseModel):
    item_id: Optional[str] = None
    description: Optional[str] = None
    quantity: Decimal = Field(gt=Decimal("0.00"))
    unit_price: Optional[Decimal] = None  # if item_id provided and unit_price omitted, we snapshot from item


class InvoiceLineOut(BaseModel):
    id: str
    invoice_id: str
    item_id: Optional[str]
    description: Optional[str]
    quantity: Decimal
    unit_price: Decimal

    class Config:
        from_attributes = True


class InvoiceWithLinesOut(InvoiceOut):
    lines: List[InvoiceLineOut] = []

    class Config:
        from_attributes = True


class StatusChangeIn(BaseModel):
    status: str = Field(..., description="draft | sent | paid | void")


# -----------------------------
# Invoice CRUD
# -----------------------------
@router.get("", response_model=List[InvoiceOut])
def list_invoices(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    invoices = db.execute(
        select(Invoice).where(Invoice.company_id == company.id).order_by(Invoice.created_at.desc())
    ).scalars().all()
    return invoices


@router.post("", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    # Ensure customer exists and belongs to company
    cust = db.execute(
        select(Customer).where(Customer.id == payload.customer_id, Customer.company_id == company.id)
    ).scalars().first()
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")

    inv = Invoice(
        id=str(uuid4()),
        company_id=company.id,
        customer_id=payload.customer_id,
        number=payload.number,
        tax_rate=payload.tax_rate,
        currency=payload.currency,
        notes=payload.notes,
        status="draft",
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


@router.get("/{invoice_id}", response_model=InvoiceWithLinesOut)
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    inv = _get_invoice(db, invoice_id)
    _ensure_company_invoice(inv, company)

    # load lines
    lines = db.execute(
        select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)
    ).scalars().all()
    inv.lines = lines  # for response model
    return inv


@router.put("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: str,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    inv = _get_invoice(db, invoice_id)
    _ensure_company_invoice(inv, company)
    _ensure_editable(inv)

    if payload.customer_id is not None:
        cust = db.execute(
            select(Customer).where(Customer.id == payload.customer_id, Customer.company_id == company.id)
        ).scalars().first()
        if not cust:
            raise HTTPException(status_code=404, detail="Customer not found")
        inv.customer_id = payload.customer_id

    if payload.number is not None:
        inv.number = payload.number

    if payload.tax_rate is not None:
        inv.tax_rate = payload.tax_rate

    if payload.currency is not None:
        inv.currency = payload.currency

    if payload.notes is not None:
        inv.notes = payload.notes

    # if tax_rate changed, totals should update
    recalc_invoice_totals(db, inv.id)

    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    inv = _get_invoice(db, invoice_id)
    _ensure_company_invoice(inv, company)
    _ensure_editable(inv)

    db.delete(inv)
    db.commit()
    return None


# -----------------------------
# Invoice Lines
# -----------------------------
@router.post("/{invoice_id}/lines", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def add_invoice_line(
    invoice_id: str,
    payload: InvoiceLineCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    inv = _get_invoice(db, invoice_id)
    _ensure_company_invoice(inv, company)
    _ensure_editable(inv)

    unit_price = payload.unit_price

    # If item_id provided and unit_price omitted, snapshot item.unit_price
    if payload.item_id:
        item = db.execute(
            select(Item).where(Item.id == payload.item_id, Item.company_id == company.id)
        ).scalars().first()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        if unit_price is None:
            unit_price = Decimal(str(item.unit_price))

        if payload.description is None:
            payload.description = item.name

    if unit_price is None:
        raise HTTPException(status_code=422, detail="unit_price is required when item_id is not provided")

    line = InvoiceLine(
        id=str(uuid4()),
        invoice_id=inv.id,
        item_id=payload.item_id,
        description=payload.description,
        quantity=payload.quantity,
        unit_price=unit_price,
    )

    db.add(line)
    db.flush()

    recalc_invoice_totals(db, inv.id)

    db.commit()
    db.refresh(inv)
    return inv


@router.delete("/{invoice_id}/lines/{line_id}")
def delete_invoice_line(
    invoice_id: str,
    line_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    inv = _get_invoice(db, invoice_id)
    _ensure_company_invoice(inv, company)
    _ensure_editable(inv)

    line = _get_line(db, line_id)
    if line.invoice_id != inv.id:
        raise HTTPException(status_code=404, detail="Invoice line not found")

    db.delete(line)
    db.flush()

    recalc_invoice_totals(db, inv.id)

    db.commit()
    return {"ok": True}


# -----------------------------
# Status transitions
# -----------------------------
@router.post("/{invoice_id}/status", response_model=InvoiceOut)
def set_invoice_status(
    invoice_id: str,
    payload: StatusChangeIn,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    new_status = payload.status.strip().lower()

    if new_status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {new_status}")

    inv = _get_invoice(db, invoice_id)
    _ensure_company_invoice(inv, company)

    current = (inv.status or "draft").lower()

    if new_status == current:
        return inv

    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid transition: {current} -> {new_status}",
        )

    # If sending/paid, make sure totals are up-to-date
    recalc_invoice_totals(db, inv.id)

    inv.status = new_status
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv
