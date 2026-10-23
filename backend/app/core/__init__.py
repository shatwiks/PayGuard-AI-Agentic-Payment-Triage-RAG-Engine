"""Core application modules."""

from backend.app.core.config import settings
from backend.app.core.database import engine, get_db, AsyncSessionLocal
from backend.app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    mask_pii,
    get_current_user,
    require_role,
)
from backend.app.core.errors import (
    PayGuardException,
    EntityNotFoundException,
    UnauthorizedException,
    ForbiddenException,
    ConflictException,
    DatabaseException,
    register_error_handlers,
)

__all__ = [
    "settings",
    "engine",
    "get_db",
    "AsyncSessionLocal",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "decode_access_token",
    "mask_pii",
    "PayGuardException",
    "EntityNotFoundException",
    "UnauthorizedException",
    "ForbiddenException",
    "ConflictException",
    "DatabaseException",
    "register_error_handlers",
]
