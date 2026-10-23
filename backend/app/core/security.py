"""Security utilities: password hashing, JWT tokens, and deterministic PII masking."""

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, List, Optional, Union
import bcrypt

from backend.app.core.config import settings

# Precompiled PII regular expressions
# Credit card regex: matches 13 to 19 digit sequences with optional hyphens/spaces
CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
# Email regex
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
# Phone regex: matches common international and domestic phone formats
PHONE_REGEX = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
# Bank account / IBAN style regex (e.g. Acc: 1234567890)
ACCOUNT_REGEX = re.compile(r"(?i)\b(?:acc(?:ount)?[\s#:]+)(\d{8,17})\b")
# SSN / Tax ID regex (###-##-####)
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


import jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against its bcrypt hash."""
    pwd_bytes = plain_password.encode("utf-8")[:72]
    hash_bytes = hashed_password.encode("utf-8")
    try:
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    """Generates bcrypt hash of password (truncated to 72 bytes per bcrypt standard)."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def create_access_token(
    subject: Union[str, Any],
    role: str = "support_agent",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generates signed HMAC-SHA256 JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "exp": expire,
        "iat": now,
        "sub": str(subject),
        "role": role,
    }
    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates JWT access token."""
    try:
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return decoded
    except (jwt.PyJWTError, ValueError):
        return None


def mask_pii(text: str) -> str:
    """Deterministic PII masking.
    Masks card numbers, emails, phone numbers, bank accounts, and SSNs.
    """
    if not settings.MASK_PII_ENABLED or not text:
        return text

    sanitized = text

    # Mask card numbers (preserve last 4 if 16 digits)
    def mask_card(match: re.Match) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) >= 13 and len(digits) <= 19:
            last4 = digits[-4:]
            return f"[CARD_REDACTED_*{last4}]"
        return match.group(0)

    sanitized = CARD_REGEX.sub(mask_card, sanitized)

    # Mask Bank Account numbers
    sanitized = ACCOUNT_REGEX.sub(r"account [ACCOUNT_ID_REDACTED]", sanitized)

    # Mask SSNs
    sanitized = SSN_REGEX.sub("[TAX_ID_REDACTED]", sanitized)

    # Mask emails
    sanitized = EMAIL_REGEX.sub("[EMAIL_REDACTED]", sanitized)

    # Mask phone numbers
    sanitized = PHONE_REGEX.sub("[PHONE_REDACTED]", sanitized)

    return sanitized


PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|prior|above|system)\s+(?:instructions|rules|prompts?)\b"),
    re.compile(r"(?i)\b(?:you\s+are\s+now|act\s+as)\s+(?:an?\s+)?(?:administrator|unrestricted|god\s+mode|root|jailbreak)\b"),
    re.compile(r"(?i)\b(?:system\s*(?:prompt|override|message)\s*:)"),
    re.compile(r"(?i)\b(?:execute\s+sql|drop\s+table|grant\s+admin|bypass\s+auth)\b"),
    re.compile(r"(?i)<\s*(?:script|iframe|object|embed)[^>]*>"),
]


def sanitize_prompt_input(text: str) -> tuple[str, bool]:
    """Detects and neutralizes prompt injection patterns in untrusted input.
    Returns (sanitized_text, injection_detected: bool).
    """
    if not text or not settings.PROMPT_INJECTION_DEFENSE_ENABLED:
        return text, False

    injection_detected = False
    sanitized = text

    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(sanitized):
            injection_detected = True
            sanitized = pattern.sub("[POTENTIAL_PROMPT_INJECTION_NEUTRALIZED]", sanitized)

    return sanitized, injection_detected




from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from backend.app.core.database import get_db
from backend.app.models.user import User

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency to extract and validate the current authenticated user."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_uuid = uuid.UUID(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed user identifier in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = select(User).where(User.id == user_uuid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user record not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return user


def require_role(allowed_roles: List[str]):
    """Role-based authorization dependency factory."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{current_user.role}' not permitted for this resource",
            )
        return current_user
    return role_checker


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """FastAPI dependency to optionally extract user if Bearer token is provided.
    If credentials are provided but invalid or expired, raises 401 Unauthorized.
    """
    if not credentials or not credentials.credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_uuid = uuid.UUID(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed user identifier in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = select(User).where(User.id == user_uuid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user record not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return user

