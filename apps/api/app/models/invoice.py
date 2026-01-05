from datetime import datetime
from uuid import uuid4
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), index=True, nullable=False)

    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), index=True, nullable=False)

    # human-friendly invoice number (optional but useful)
    number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, server_default="0.0000")

    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0.00")
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0.00")
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0.00")

    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")  # draft|sent|paid|void

    currency: Mapped[str] = mapped_column(String(10), nullable=False, server_default="USD")

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # relationships
    lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")
    customer = relationship("Customer")