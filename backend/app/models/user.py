"""User model representing payment support and operations personnel."""

import uuid
from typing import List, TYPE_CHECKING
from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, GUID, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.investigation import InvestigationCase
    from backend.app.models.audit import AuditEvent
    from backend.app.models.knowledge import KnowledgeDocument


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('support_agent', 'compliance_analyst', 'admin')",
            name="ck_users_role_valid"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    full_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(32),
        default="support_agent",
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    # Relationships
    assigned_cases: Mapped[List["InvestigationCase"]] = relationship(
        "InvestigationCase",
        back_populates="created_by",
        lazy="selectin"
    )
    audit_events: Mapped[List["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="user",
        lazy="selectin"
    )
    uploaded_documents: Mapped[List["KnowledgeDocument"]] = relationship(
        "KnowledgeDocument",
        foreign_keys="KnowledgeDocument.uploaded_by_id",
        back_populates="uploaded_by",
        lazy="selectin"
    )
