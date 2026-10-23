"""PayGuard AI error hierarchy and standardized HTTP exception handlers."""

from typing import Any, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.schemas.common import ErrorDetail, ErrorResponse


class PayGuardException(Exception):
    """Base exception for all PayGuard domain errors."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class EntityNotFoundException(PayGuardException):
    """Raised when an entity is not found in database."""
    def __init__(self, entity_name: str, identifier: Any = ""):
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' was not found.",
            code="ENTITY_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnauthorizedException(PayGuardException):
    """Raised when authentication or token validation fails."""
    def __init__(self, message: str = "Invalid credentials or missing token"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenException(PayGuardException):
    """Raised when user lacks permission to access resource."""
    def __init__(self, message: str = "Insufficient permissions to perform this action"):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ConflictException(PayGuardException):
    """Raised when creating an entity that violates unique constraints."""
    def __init__(self, message: str = "Resource conflict or duplicate entry"):
        super().__init__(
            message=message,
            code="RESOURCE_CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
        )


class DatabaseException(PayGuardException):
    """Raised when database query or connection fails."""
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def register_error_handlers(app: FastAPI) -> None:
    """Registers standard RFC 7807 error envelopes for all custom and validation exceptions."""

    @app.exception_handler(PayGuardException)
    async def payguard_exception_handler(request: Request, exc: PayGuardException):
        response_model = ErrorResponse(
            error=ErrorDetail(code=exc.code, message=exc.message)
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=response_model.model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        first_error = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(loc) for loc in first_error.get("loc", []))
        message = first_error.get("msg", "Invalid request parameter")
        response_model = ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message=message,
                field=field,
            )
        )
        status_code = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        return JSONResponse(
            status_code=status_code,
            content=response_model.model_dump(mode="json"),
        )
