"""Document ingestion, chunking, and re-embedding pipeline for PayGuard AI RAG."""

import hashlib
import logging
from typing import List, Optional
import uuid
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.knowledge import DocumentChunk, KnowledgeDocument
from backend.app.services.chunker import DocumentChunker
from backend.app.services.embedding import IEmbeddingProvider, get_embedding_provider

logger = logging.getLogger("payguard.ingestion")


class IngestionDocumentRequest(BaseModel):
    """Payload to ingest an authoritative knowledge document."""
    title: str = Field(min_length=3, max_length=255, description="Document title")
    doc_type: str = Field(description="Document type: scheme_rules, refund_policy, dispute_guide, sla_spec")
    version: str = Field(description="Semantic version string e.g. 1.0 or 2026.1")
    source_id: str = Field(description="Stable source identifier e.g. internal://policies/nacha_ach")
    source_url: Optional[str] = Field(default=None, description="Canonical source URL or internal URI")
    raw_content: str = Field(min_length=10, description="Full text or Markdown body of document")


class IngestionResult(BaseModel):
    """Result summary of document ingestion."""
    document_id: uuid.UUID
    title: str
    source_id: str
    chunks_count: int
    embeddings_generated: bool
    embedding_model: Optional[str] = None
    status: str = Field(description="Ingestion status: success, skipped_unchanged, lexical_only, failed")
    message: str


class DocumentIngestionPipeline:
    """Manages document validation, normalization, section-aware chunking, and pgvector persistence."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: Optional[IEmbeddingProvider] = None,
        chunker: Optional[DocumentChunker] = None,
    ):
        self.session = session
        self.provider = embedding_provider or get_embedding_provider()
        self.chunker = chunker or DocumentChunker()

    async def ingest_document(
        self,
        request: IngestionDocumentRequest,
        force_reindex: bool = False,
    ) -> IngestionResult:
        """Ingests a document with deduplication, chunking, and optional vector generation."""
        content_hash = hashlib.sha256(request.raw_content.encode("utf-8")).hexdigest()

        # Check for existing document by source_id or title
        stmt = (
            select(KnowledgeDocument)
            .where(
                (KnowledgeDocument.source_id == request.source_id)
                | (KnowledgeDocument.title == request.title)
            )
            .options(selectinload(KnowledgeDocument.chunks))
        )
        existing_doc = (await self.session.execute(stmt)).scalar_one_or_none()

        target_model = self.provider.model_name if self.provider.is_available else None

        # Check if unchanged document already has embeddings matching target model
        if existing_doc and not force_reindex:
            if existing_doc.content_hash == content_hash and existing_doc.chunks:
                # Check if chunks already have valid embeddings for current model
                all_embedded = all(c.embedding_model == target_model for c in existing_doc.chunks)
                if (self.provider.is_available and all_embedded) or (not self.provider.is_available and not all_embedded):
                    return IngestionResult(
                        document_id=existing_doc.id,
                        title=existing_doc.title,
                        source_id=request.source_id,
                        chunks_count=len(existing_doc.chunks),
                        embeddings_generated=all_embedded,
                        embedding_model=target_model,
                        status="skipped_unchanged",
                        message="Document content and embeddings are up-to-date. Skipped re-embedding.",
                    )

        # 1. Normalize and chunk text
        chunks = self.chunker.split_document(
            text=request.raw_content,
            document_title=request.title,
            source_id=request.source_id,
        )

        if not chunks:
            raise ValueError(f"Document '{request.title}' yielded no valid text chunks after normalization")

        # 2. Generate embeddings if provider is available
        embeddings_generated = False
        chunk_embeddings: List[Optional[List[float]]] = [None] * len(chunks)

        if self.provider.is_available:
            try:
                texts = [c.content for c in chunks]
                vectors = await self.provider.embed_batch(texts)
                chunk_embeddings = [self.provider.validate_vector(v) for v in vectors]
                embeddings_generated = True
            except Exception as e:
                logger.warning(
                    f"Embedding generation failed for '{request.title}', persisting in lexical-only mode: {e}"
                )
                embeddings_generated = False
                target_model = None

        # 3. Persist document and chunks transactionally
        doc_id = existing_doc.id if existing_doc else uuid.uuid4()

        if existing_doc:
            existing_doc.title = request.title
            existing_doc.doc_type = request.doc_type
            existing_doc.version = request.version
            existing_doc.source_id = request.source_id
            existing_doc.source_url = request.source_url
            existing_doc.content_hash = content_hash
            existing_doc.raw_content = request.raw_content
            # Clear existing chunks
            for old_chunk in list(existing_doc.chunks):
                await self.session.delete(old_chunk)
            doc_obj = existing_doc
        else:
            doc_obj = KnowledgeDocument(
                id=doc_id,
                title=request.title,
                doc_type=request.doc_type,
                version=request.version,
                source_id=request.source_id,
                source_url=request.source_url,
                content_hash=content_hash,
                raw_content=request.raw_content,
                is_active=True,
            )
            self.session.add(doc_obj)

        await self.session.flush()

        # Insert new chunks
        for idx, chunk in enumerate(chunks):
            db_chunk = DocumentChunk(
                id=uuid.uuid4(),
                document_id=doc_id,
                chunk_index=chunk.chunk_index,
                section_header=chunk.section_header,
                content=chunk.content,
                token_count=chunk.token_count,
                embedding=chunk_embeddings[idx] if embeddings_generated else None,
                embedding_model=target_model if embeddings_generated else None,
                metadata_={
                    **chunk.metadata,
                    "doc_type": request.doc_type,
                    "version": request.version,
                    "source_id": request.source_id,
                    "provenance": "verified_ingestion",
                },
            )
            self.session.add(db_chunk)

        await self.session.commit()

        status_str = "success" if embeddings_generated else "lexical_only"
        msg = (
            f"Successfully ingested and embedded {len(chunks)} chunks with model '{target_model}'."
            if embeddings_generated
            else f"Ingested {len(chunks)} chunks in lexical-only mode (real embedding provider offline)."
        )

        return IngestionResult(
            document_id=doc_id,
            title=request.title,
            source_id=request.source_id,
            chunks_count=len(chunks),
            embeddings_generated=embeddings_generated,
            embedding_model=target_model,
            status=status_str,
            message=msg,
        )
