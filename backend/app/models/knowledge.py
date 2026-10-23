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
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.schema import FetchedValue
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, GUID, TimestampMixin

JSONType = JSONB().with_variant(JSON(), "sqlite")
TSVectorType = TSVECTOR().with_variant(Text(), "sqlite")

try:
    from pgvector.sqlalchemy import Vector
    # Vector column with 1536 dimensions (compatible with pgvector and SQLite JSON variant)
    VectorColumn = Vector(1536).with_variant(JSON(), "sqlite")
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

    @property
    def source_type(self) -> str:
        return self.doc_type
    version: Mapped[str] = mapped_column(
        String(32),
        nullable=False
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True
    )
    source_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        index=True,
        nullable=True
    )
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    raw_content: Mapped[Optional[str]] = mapped_column(
        Text,
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
    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(64),
        index=True,
        nullable=True
    )
    tsv: Mapped[Optional[Any]] = mapped_column(
        TSVectorType,
        server_default=FetchedValue(),
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

    def __init__(self, **kwargs: Any):
        source_id = kwargs.pop("source_id", None)
        if source_id:
            meta = kwargs.setdefault("metadata_", {})
            if isinstance(meta, dict):
                meta.setdefault("source_id", source_id)
        super().__init__(**kwargs)

    @property
    def source_id(self) -> Optional[str]:
        if self.document and self.document.source_id:
            return self.document.source_id
        if self.metadata_ and isinstance(self.metadata_, dict):
            return self.metadata_.get("source_id")
        return None
