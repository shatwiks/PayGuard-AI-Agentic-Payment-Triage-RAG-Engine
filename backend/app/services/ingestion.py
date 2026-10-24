"""Document ingestion, chunking, and re-embedding pipeline for PayGuard AI RAG."""

from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.knowledge import DocumentChunk, KnowledgeDocument
from backend.app.services.chunker import DocumentChunker, TextChunk
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
    model_config = ConfigDict(arbitrary_types_allowed=True)

    document_id: uuid.UUID
    title: str
    source_id: str
    chunks_count: int
    embeddings_generated: bool
    embedding_model: Optional[str] = None
    status: str = Field(description="Ingestion status: success, skipped_unchanged, lexical_only, failed")
    message: str
    document: Optional[Any] = None
    chunks: Optional[List[Any]] = None
    parent_chunks: Optional[List[Any]] = None
    child_chunks: Optional[List[Any]] = None

    def __iter__(self):
        yield self.document
        yield self.chunks or []


class DocumentIngestionPipeline:
    """Manages document validation, normalization, hierarchical chunking, and pgvector persistence."""

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
        request: Optional[IngestionDocumentRequest] = None,
        *,
        title: Optional[str] = None,
        doc_type: str = "scheme_rules",
        source_type: Optional[str] = None,
        version: str = "1.0",
        source_id: Optional[str] = None,
        source_url: Optional[str] = None,
        raw_content: Optional[str] = None,
        content: Optional[str] = None,
        metadata: Optional[dict] = None,
        force_reindex: bool = False,
        hierarchical: bool = False,
    ) -> IngestionResult:
        """Ingests a document with deduplication, chunking, and optional vector generation."""
        if request is None:
            effective_content = raw_content or content or ""
            effective_source_id = source_id or f"internal://policies/{(title or 'doc').lower().replace(' ', '-')}"
            request = IngestionDocumentRequest(
                title=title or "Untitled Document",
                doc_type=source_type or doc_type,
                version=version,
                source_id=effective_source_id,
                source_url=source_url,
                raw_content=effective_content,
            )

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
                        document=existing_doc,
                        chunks=list(existing_doc.chunks),
                    )

        # 1. Normalize and chunk text
        if hierarchical:
            hierarchical_res = self.chunker.split_hierarchical(
                text=request.raw_content,
                document_title=request.title,
                source_id=request.source_id,
                metadata=metadata,
            )
            parent_text_chunks = hierarchical_res.parents
            child_text_chunks = hierarchical_res.children
            text_chunks = hierarchical_res.all_chunks
        else:
            text_chunks = self.chunker.split_document(
                text=request.raw_content,
                document_title=request.title,
                source_id=request.source_id,
                metadata=metadata,
            )
            parent_text_chunks = []
            child_text_chunks = text_chunks

        if not text_chunks:
            raise ValueError(f"Document '{request.title}' yielded no valid text chunks after normalization")

        # 2. Generate embeddings if provider is available
        embeddings_generated = False
        chunk_embeddings: List[Optional[List[float]]] = [None] * len(text_chunks)

        if self.provider.is_available:
            try:
                # Generate embeddings for text chunks
                texts = [c.content for c in text_chunks]
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

        # 4. Insert chunks with parent-child linkage
        created_chunks: List[DocumentChunk] = []
        created_parent_chunks: List[DocumentChunk] = []
        created_child_chunks: List[DocumentChunk] = []

        if hierarchical:
            # First pass: Create and persist parent chunks to get their database IDs
            parent_id_map: Dict[int, uuid.UUID] = {}
            for idx, p_chunk in enumerate(parent_text_chunks):
                p_id = uuid.uuid4()
                parent_id_map[p_chunk.chunk_index] = p_id

                # Match embedding if computed
                p_emb = chunk_embeddings[idx] if embeddings_generated and idx < len(chunk_embeddings) else None

                db_parent = DocumentChunk(
                    id=p_id,
                    document_id=doc_id,
                    parent_chunk_id=None,
                    chunk_type="parent",
                    chunk_index=p_chunk.chunk_index,
                    section_header=p_chunk.section_header,
                    section_title=p_chunk.section_title or p_chunk.section_header,
                    content=p_chunk.content,
                    content_hash=p_chunk.content_hash,
                    token_count=p_chunk.token_count,
                    embedding=p_emb,
                    embedding_model=target_model if embeddings_generated and p_emb else None,
                    metadata_={
                        **p_chunk.metadata,
                        "doc_type": request.doc_type,
                        "version": request.version,
                        "source_id": request.source_id,
                        "provenance": "verified_ingestion",
                    },
                )
                self.session.add(db_parent)
                created_parent_chunks.append(db_parent)
                created_chunks.append(db_parent)

            await self.session.flush()

            # Second pass: Create child chunks linking to parents
            child_offset = len(parent_text_chunks)
            for c_idx, c_chunk in enumerate(child_text_chunks):
                parent_db_id = parent_id_map.get(c_chunk.parent_index)
                emb_idx = child_offset + c_idx
                c_emb = chunk_embeddings[emb_idx] if embeddings_generated and emb_idx < len(chunk_embeddings) else None

                db_child = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc_id,
                    parent_chunk_id=parent_db_id,
                    chunk_type="child",
                    chunk_index=c_chunk.chunk_index,
                    section_header=c_chunk.section_header,
                    section_title=c_chunk.section_title or c_chunk.section_header,
                    content=c_chunk.content,
                    content_hash=c_chunk.content_hash,
                    token_count=c_chunk.token_count,
                    embedding=c_emb,
                    embedding_model=target_model if embeddings_generated and c_emb else None,
                    metadata_={
                        **c_chunk.metadata,
                        "doc_type": request.doc_type,
                        "version": request.version,
                        "source_id": request.source_id,
                        "parent_chunk_id": str(parent_db_id) if parent_db_id else None,
                        "provenance": "verified_ingestion",
                    },
                )
                self.session.add(db_child)
                created_child_chunks.append(db_child)
                created_chunks.append(db_child)
        else:
            # Standalone flat chunking
            for idx, chunk in enumerate(text_chunks):
                db_chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc_id,
                    parent_chunk_id=None,
                    chunk_type="standalone",
                    chunk_index=chunk.chunk_index,
                    section_header=chunk.section_header,
                    section_title=chunk.section_title or chunk.section_header,
                    content=chunk.content,
                    content_hash=chunk.content_hash,
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
                created_chunks.append(db_chunk)
                created_child_chunks.append(db_chunk)

        await self.session.commit()

        status_str = "success" if embeddings_generated else "lexical_only"
        msg = (
            f"Successfully ingested and embedded {len(created_chunks)} chunks with model '{target_model}'."
            if embeddings_generated
            else f"Ingested {len(created_chunks)} chunks in lexical-only mode (real embedding provider offline)."
        )

        return IngestionResult(
            document_id=doc_id,
            title=request.title,
            source_id=request.source_id,
            chunks_count=len(created_chunks),
            embeddings_generated=embeddings_generated,
            embedding_model=target_model,
            status=status_str,
            message=msg,
            document=doc_obj,
            chunks=created_chunks,
            parent_chunks=created_parent_chunks if hierarchical else None,
            child_chunks=created_child_chunks if hierarchical else created_chunks,
        )

    async def ingest_hierarchical_document(
        self,
        title: str,
        content: str,
        source_id: Optional[str] = None,
        doc_type: str = "scheme_rules",
        version: str = "1.0",
        source_url: Optional[str] = None,
        metadata: Optional[dict] = None,
        force_reindex: bool = False,
    ) -> IngestionResult:
        """Convenience method to ingest a document with parent-child hierarchical chunking enabled."""
        return await self.ingest_document(
            title=title,
            raw_content=content,
            source_id=source_id,
            doc_type=doc_type,
            version=version,
            source_url=source_url,
            metadata=metadata,
            force_reindex=force_reindex,
            hierarchical=True,
        )
