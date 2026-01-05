from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt only uses the first 72 bytes of input. Passlib raises if >72 bytes.
BCRYPT_MAX_BYTES = 72


def _check_bcrypt_length(password: str) -> None:
    if password is None:
        raise ValueError("Password is required")
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > BCRYPT_MAX_BYTES:
        raise ValueError(
            f"Password too long for bcrypt: {len(pw_bytes)} bytes (max {BCRYPT_MAX_BYTES})."
        )


def hash_password(password: str) -> str:
    _check_bcrypt_length(password)
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # If a user enters something >72 bytes, don't crash; just fail auth.
    try:
        _check_bcrypt_length(plain_password)
    except ValueError:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str,
    secret_key: str,
    expires_minutes: int = 60,
    algorithm: str = "HS256",
    additional_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    Create a JWT access token.
    - subject: typically the user_id
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=int(expires_minutes))

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(payload, secret_key, algorithm=algorithm)
