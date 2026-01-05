from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company, get_current_user
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.company import Company
from app.models.membership import Membership
from app.models.user import User

# ? No prefix here. Prefix is applied in app/api/router.py
router = APIRouter(tags=["auth"])


# -----------------------------
# Schemas
# -----------------------------
class RegisterIn(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    user_id: str
    email: EmailStr
    company_id: str
    company_name: str


# -----------------------------
# Routes
# -----------------------------
@router.get("/ping")
def ping():
    return {"ok": True}


@router.post("/register", response_model=TokenOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    email = str(payload.email).lower().strip()

    # email must be unique
    existing = db.execute(select(User).where(User.email == email)).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
      
    try:
        pw_hash = hash_password(payload.password)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)
        )

    # Create company
    company = Company(
        id=str(uuid4()),
        name=payload.company_name.strip(),
    )
    
    db.add(company)

    # Create user
    user = User(
        id=str(uuid4()),
        email=email,
        password_hash=hash_password(payload.password),
        is_active=True,
        is_superuser=False,
    )

    db.add(user)

    # Membership (owner)
    membership = Membership(
        id=str(uuid4()),
        company_id=company.id,
        user_id=user.id,
        role="owner",
    )

    db.add(membership)

    db.commit()

    token = create_access_token(
        subject=user.id,
        secret_key=settings.API_SECRET_KEY,
        expires_minutes=settings.API_ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    return TokenOut(access_token=token)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    email = str(payload.email).lower().strip()

    user = db.execute(select(User).where(User.email == email)).scalars().first()
    if not user or not getattr(user, "password_hash", None):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if hasattr(user, "is_active") and not user.is_active:
        raise HTTPException(status_code=403, detail="User is disabled")

    token = create_access_token(
        subject=user.id,
        secret_key=settings.API_SECRET_KEY,
        expires_minutes=settings.API_ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    return TokenOut(access_token=token)


@router.get("/me", response_model=MeOut)
def me(
    user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
):
    return MeOut(
        user_id=user.id,
        email=user.email,
        company_id=company.id,
        company_name=company.name,
    )
