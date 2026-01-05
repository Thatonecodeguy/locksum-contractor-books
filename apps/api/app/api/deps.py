from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.models.company import Company
from app.models.membership import Membership


def _get_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return parts[1].strip()


def get_current_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
) -> User:
    token = _get_bearer_token(authorization)
    try:
        payload = jwt.decode(token, settings.API_SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token subject")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if hasattr(user, "is_active") and not user.is_active:
        raise HTTPException(status_code=403, detail="User is disabled")

    return user


def get_current_company(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Company:
    stmt = (
        select(Company)
        .join(Membership, Membership.company_id == Company.id)
        .where(Membership.user_id == user.id)
        .limit(1)
    )
    company = db.execute(stmt).scalars().first()
    if not company:
        raise HTTPException(status_code=400, detail="User has no company membership")
    return company
