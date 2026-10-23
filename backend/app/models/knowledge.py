"""KnowledgeDocument and DocumentChunk models with pgvector embedding support."""

from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
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

JSONType = JSONB().with_variant(JSON(), "sqlite")

try:
    from pgvector.sqlalchemy import Vector
    # Vector column with 1536 dimensions (compatible with text-embedding-3-small and standard embeddings)
    VectorColumn = Vector(1536).with_variant(JSONType, "sqlite")
except ImportError:
    VectorColumn = JSONType


class KnowledgeDocument(Base, TimestampMixin):
    """Authoritative compliance, dispute, and troubleshooting document."""
    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    doc_type: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False
    )  # scheme_rules, refund_policy, dispute_guide, sla_spec
    version: Mapped[str] = mapped_column(
        String(32),
        nullable=False
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    # Relationship
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index"
    )


class DocumentChunk(Base):
    """Chunked passages with pgvector embeddings for hybrid RAG retrieval."""
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("idx_chunks_document_index", "document_id", "chunk_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    section_header: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    embedding: Mapped[Any] = mapped_column(
        VectorColumn,
        nullable=True
    )
    metadata_: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONType,
        default=dict,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    # Relationship
    document: Mapped["KnowledgeDocument"] = relationship(
        "KnowledgeDocument",
        back_populates="chunks"
    )
