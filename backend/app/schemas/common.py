"""Common schemas for pagination, standard error envelopes, and health checks."""

from datetime import datetime, timezone
import math
from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Standard URL query parameters for list pagination."""
    page: int = Field(default=1, ge=1, description="Page number starting at 1")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")


class PaginatedResponse(BaseModel, Generic[T]):
    """Consistent envelope for paginated resource collections."""
    model_config = ConfigDict(from_attributes=True)

    items: List[T] = Field(description="List of records for current page")
    total: int = Field(ge=0, description="Total matching items across all pages")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, description="Maximum items per page")
    total_pages: int = Field(ge=0, description="Total pages calculated from total / page_size")

    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int) -> "PaginatedResponse[T]":
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )


class ErrorDetail(BaseModel):
    code: str = Field(description="Machine-readable error identifier")
    message: str = Field(description="Human-readable description of the error")
    field: Optional[str] = Field(default=None, description="Specific field causing validation error")


class ErrorResponse(BaseModel):
    """Standard RFC 7807-inspired error response envelope."""
    error: ErrorDetail
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HealthResponse(BaseModel):
    """Liveness and readiness check response."""
    status: str = Field(example="healthy")
    database: str = Field(example="connected")
    vector_store: str = Field(example="pgvector_ready")
    version: str = Field(example="0.1.0")
    environment: str = Field(example="development")
