from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company, get_current_user
from app.db.session import get_db
from app.models.company import Company
from app.models.customer import Customer

router = APIRouter(prefix="/customers", tags=["customers"])


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None


class CustomerOut(BaseModel):
    id: str
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("", response_model=List[CustomerOut])
def list_customers(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    _user=Depends(get_current_user),
):
    stmt = select(Customer).where(Customer.company_id == company.id).order_by(Customer.name.asc())
    return db.execute(stmt).scalars().all()


@router.post("", response_model=CustomerOut)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    _user=Depends(get_current_user),
):
    customer = Customer(
        id=str(uuid4()),
        company_id=company.id,
        name=payload.name.strip(),
        email=str(payload.email).lower().strip() if payload.email else None,
        phone=payload.phone,
        address1=payload.address1,
        address2=payload.address2,
        city=payload.city,
        state=payload.state,
        zip=payload.zip,
        country=payload.country,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    _user=Depends(get_current_user),
):
    customer = db.get(Customer, customer_id)
    if not customer or customer.company_id != company.id:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    _user=Depends(get_current_user),
):
    customer = db.get(Customer, customer_id)
    if not customer or customer.company_id != company.id:
        raise HTTPException(status_code=404, detail="Customer not found")

    for k, v in payload.model_dump(exclude_unset=True).items():
        if k == "email" and v is not None:
            v = str(v).lower().strip()
        setattr(customer, k, v)

    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}")
def delete_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    _user=Depends(get_current_user),
):
    customer = db.get(Customer, customer_id)
    if not customer or customer.company_id != company.id:
        raise HTTPException(status_code=404, detail="Customer not found")

    db.delete(customer)
    db.commit()
    return {"deleted": True}
