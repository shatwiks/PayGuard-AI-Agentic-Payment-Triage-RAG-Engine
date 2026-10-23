"""Payment and PaymentEvent models for transaction ledger and event telemetry."""

from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from decimal import Decimal
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, GUID, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.investigation import InvestigationCase


# Use JSONB on PostgreSQL, standard JSON elsewhere (e.g. SQLite for fast tests)
JSONType = JSONB().with_variant(JSON(), "sqlite")


class Payment(Base, TimestampMixin):
    """Authoritative payment transaction record."""
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('authorized', 'captured', 'failed', 'pending', 'refunded', 'partially_refunded', 'disputed')",
            name="ck_payments_status_valid"
        ),
        CheckConstraint(
            "payment_method IN ('credit_card', 'debit_card', 'ach', 'upi', 'wire')",
            name="ck_payments_method_valid"
        ),
        Index("idx_payments_customer_created", "customer_id", "created_at"),
        Index("idx_payments_merchant_status", "merchant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    payment_reference: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )
    customer_id: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False
    )
    merchant_id: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False
    )
    payment_method: Mapped[str] = mapped_column(
        String(32),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False
    )
    gateway_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    gateway_transaction_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        index=True,
        nullable=True
    )
    failure_code: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    failure_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    metadata_: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONType,
        default=dict,
        nullable=False
    )
    authorized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    captured_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    events: Mapped[List["PaymentEvent"]] = relationship(
        "PaymentEvent",
        back_populates="payment",
        cascade="all, delete-orphan",
        order_by="PaymentEvent.occurred_at"
    )
    investigations: Mapped[List["InvestigationCase"]] = relationship(
        "InvestigationCase",
        back_populates="payment"
    )


class PaymentEvent(Base):
    """Payment status transition history and gateway webhook event log."""
    __tablename__ = "payment_events"
    __table_args__ = (
        Index("idx_payment_events_payment_occurred", "payment_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("payments.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    from_status: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True
    )
    to_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False
    )
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONType,
        default=dict,
        nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    # Relationship
    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="events"
    )
