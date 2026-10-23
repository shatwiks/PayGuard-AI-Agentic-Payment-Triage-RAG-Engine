"""InvestigationCase and InvestigationResult models for payment support workflows."""

import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, GUID, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.user import User
    from backend.app.models.payment import Payment
    from backend.app.models.audit import AuditEvent

JSONType = JSONB().with_variant(JSON(), "sqlite")


class InvestigationCase(Base, TimestampMixin):
    """Lifecycle tracking for a customer payment issue investigation."""
    __tablename__ = "investigation_cases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'in_progress', 'triaged', 'escalated', 'closed')",
            name="ck_cases_status_valid"
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name="ck_cases_priority_valid"
        ),
        Index("idx_cases_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    case_number: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("payments.id", ondelete="SET NULL"),
        index=True,
        nullable=True
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True
    )
    customer_query: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    sanitized_query: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="open",
        nullable=False
    )
    priority: Mapped[str] = mapped_column(
        String(32),
        default="medium",
        nullable=False
    )

    # Relationships
    payment: Mapped[Optional["Payment"]] = relationship(
        "Payment",
        back_populates="investigations"
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="assigned_cases"
    )
    result: Mapped[Optional["InvestigationResult"]] = relationship(
        "InvestigationResult",
        back_populates="case",
        uselist=False,
        cascade="all, delete-orphan"
    )
    audit_events: Mapped[List["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="case"
    )


class InvestigationResult(Base):
    """Structured evidence, citations, and recommendations produced by the triage engine and LLM."""
    __tablename__ = "investigation_results"
    __table_args__ = (
        CheckConstraint(
            "issue_category IN ('failed_payment', 'pending_payment', 'duplicate_charge', 'refund_status', 'unknown_or_other')",
            name="ck_results_category_valid"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("investigation_cases.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False
    )
    issue_category: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    investigation_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    recommended_action: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    recommended_action_details: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    policy_citations: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONType,
        default=list,
        nullable=False
    )
    missing_or_conflicting_info: Mapped[List[str]] = mapped_column(
        JSONType,
        default=list,
        nullable=False
    )
    human_review_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    human_review_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    execution_time_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    llm_model_name: Mapped[str] = mapped_column(
        String(64),
        default="gpt-4o-mini",
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    # Relationship
    case: Mapped["InvestigationCase"] = relationship(
        "InvestigationCase",
        back_populates="result"
    )
