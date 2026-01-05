from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine


def recalc_invoice_totals(db: Session, invoice_id: str) -> Invoice:
    """
    Recalculate invoice subtotal, tax, and total from invoice lines.
    Uses snapshot values stored on InvoiceLine.
    """

    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    ).scalars().first()

    if not invoice:
        raise ValueError("Invoice not found")

    lines = db.execute(
        select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)
    ).scalars().all()

    subtotal = Decimal("0.00")

    for line in lines:
        qty = Decimal(str(line.quantity))
        price = Decimal(str(line.unit_price))
        subtotal += qty * price

    tax_rate = Decimal(str(invoice.tax_rate or 0))
    tax_total = (subtotal * tax_rate).quantize(Decimal("0.01"))
    total = (subtotal + tax_total).quantize(Decimal("0.01"))

    invoice.subtotal = subtotal
    invoice.tax_total = tax_total
    invoice.total = total

    db.add(invoice)
    db.flush()  # no commit here (caller controls transaction)

    return invoice
