"""AuditEvent model for immutable operations logging and compliance tracking."""

from datetime import datetime
import uuid
from typing import Any, Dict, Optional, TYPE_CHECKING
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, GUID

if TYPE_CHECKING:
    from backend.app.models.investigation import InvestigationCase
    from backend.app.models.user import User

JSONType = JSONB().with_variant(JSON(), "sqlite")


class AuditEvent(Base):
    """Immutable audit trail of all investigation actions, tool executions, and security events."""
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("idx_audit_case_action", "case_id", "action"),
        Index("idx_audit_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("investigation_cases.id", ondelete="SET NULL"),
        index=True,
        nullable=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True
    )
    action: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False
    )  # query_intake, payment_lookup, triage_classified, rag_retrieval, llm_reasoning, case_closed
    resource_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True
    )
    details: Mapped[Dict[str, Any]] = mapped_column(
        JSONType,
        default=dict,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        index=True,
        nullable=False
    )

    # Relationships
    case: Mapped[Optional["InvestigationCase"]] = relationship(
        "InvestigationCase",
        back_populates="audit_events"
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_events"
    )
