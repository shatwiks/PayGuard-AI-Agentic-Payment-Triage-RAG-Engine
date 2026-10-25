"""Document ingestion, chunking, and re-embedding pipeline for PayGuard AI RAG."""

from datetime import datetime, timezone
import asyncio
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import os

from backend.app.core.config import settings
from backend.app.models.knowledge import DocumentChunk, KnowledgeDocument
from backend.app.services.chunker import DocumentChunker, HierarchicalChunk, TextChunk
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
        try:
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
                    is_system=True,
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
        except Exception as e:
            await self.session.rollback()
            logger.error("Database persistence failed for document '%s': %s", request.title, e)
            raise

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

    async def ingest_user_uploaded_file(
        self,
        file_bytes: bytes,
        filename: str,
        user_id: uuid.UUID,
        doc_type: str = "user_upload",
        title: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> IngestionResult:
        """Parses, stores, hierarchically chunks, embeds, and indexes a user-uploaded document."""
        from backend.app.services.document_parser import DocumentParser

        parser = DocumentParser()
        parsed = await asyncio.to_thread(
            parser.parse,
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type,
        )

        # 1. Duplicate detection: Check if this user already uploaded identical file content
        stmt = (
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.content_hash == parsed.content_hash,
                KnowledgeDocument.uploaded_by_id == user_id,
                KnowledgeDocument.is_active.is_(True),
            )
            .options(selectinload(KnowledgeDocument.chunks))
        )
        res = await self.session.execute(stmt)
        existing_doc = res.scalar_one_or_none()

        if existing_doc:
            logger.info("Duplicate document detected for user %s: %s (%s)", user_id, existing_doc.id, filename)
            return IngestionResult(
                document_id=existing_doc.id,
                title=existing_doc.title,
                source_id=existing_doc.source_id or f"user://upload/{existing_doc.id}",
                chunks_count=existing_doc.chunk_count,
                embeddings_generated=existing_doc.embedding_status in ("embedded", "completed"),
                embedding_model=self.provider.model_name if self.provider.is_available else None,
                status="skipped_unchanged",
                message="Duplicate document detected; returning existing record.",
                document=existing_doc,
                chunks=existing_doc.chunks,
            )

        # 2. Secure file storage path
        os.makedirs(settings.UPLOAD_STORAGE_DIR, exist_ok=True)
        doc_id = uuid.uuid4()
        safe_filename = parser.sanitize_filename(filename)
        storage_filename = f"{doc_id}_{safe_filename}"
        storage_path = os.path.join(settings.UPLOAD_STORAGE_DIR, storage_filename)

        def _write_file_sync(path: str, data: bytes) -> None:
            with open(path, "wb") as f:
                f.write(data)

        try:
            await asyncio.to_thread(_write_file_sync, storage_path, file_bytes)
        except Exception as write_err:
            logger.error("Failed to write uploaded file to storage: %s", write_err)
            raise

        try:
            # 3. Create document record with pending status
            effective_title = title or os.path.splitext(safe_filename)[0]
            doc_obj = KnowledgeDocument(
                id=doc_id,
                title=effective_title,
                doc_type=doc_type,
                version="1.0",
                source_id=f"user://upload/{doc_id}",
                source_url=None,
                content_hash=parsed.content_hash,
                raw_content=parsed.raw_content,
                is_active=True,
                uploaded_by_id=user_id,
                is_system=False,
                file_name=safe_filename,
                file_size_bytes=parsed.file_size_bytes,
                mime_type=parsed.mime_type,
                storage_path=storage_path,
                page_count=parsed.page_count,
                processing_status="processing",
                embedding_status="pending",
                chunk_count=0,
            )
            self.session.add(doc_obj)
            await self.session.flush()

            # 4. Hierarchical Chunking
            doc_metadata = {
                "source_document": effective_title,
                "file_name": safe_filename,
                "user_id": str(user_id),
            }
            h_res = self.chunker.split_hierarchical(
                text=parsed.raw_content,
                document_title=effective_title,
                metadata=doc_metadata,
            )

            parent_chunks = h_res.parents
            child_chunks = h_res.children

            if not child_chunks:
                flat_chunks = self.chunker.split_document(parsed.raw_content)
                child_chunks = [
                    HierarchicalChunk(
                        content=fc.content,
                        chunk_index=fc.chunk_index,
                        chunk_type="child",
                        parent_index=None,
                        section_header=fc.section_header,
                        token_count=fc.token_count,
                        metadata=fc.metadata,
                    )
                    for fc in flat_chunks
                ]

            # Assign page numbers based on parsed page boundaries with header-stripping and token fallback
            normalized_pages = [
                (p_num, re.sub(r"\s+", " ", p_text).strip().lower())
                for p_num, p_text in parsed.pages
            ]
            for c in child_chunks + parent_chunks:
                clean_body = re.sub(r"^#+\s*", "", c.content.strip(), flags=re.MULTILINE)
                clean_norm = re.sub(r"\s+", " ", clean_body).strip().lower()
                snippet_long = clean_norm[:60].strip()
                snippet_short = clean_norm[:30].strip()
                matched_page = None
                for p_num, p_norm in normalized_pages:
                    if (snippet_long and snippet_long in p_norm) or (snippet_short and snippet_short in p_norm):
                        matched_page = p_num
                        break
                if matched_page is None and normalized_pages:
                    # Fallback: pick page with highest token overlap
                    chunk_tokens = set(re.findall(r"[a-z0-9]{3,}", clean_norm[:200]))
                    if chunk_tokens:
                        best_page, best_overlap = None, 0
                        for p_num, p_norm in normalized_pages:
                            overlap = sum(1 for tok in chunk_tokens if tok in p_norm)
                            if overlap > best_overlap:
                                best_overlap = overlap
                                best_page = p_num
                        if best_page is not None and best_overlap > 0:
                            matched_page = best_page
                if matched_page:
                    c.metadata["page_number"] = matched_page

            # 5. Embeddings Generation (if provider configured and available)
            embeddings_generated = False
            target_model = self.provider.model_name if self.provider.is_available else None
            child_embeddings: List[Optional[List[float]]] = [None] * len(child_chunks)

            if self.provider.is_available:
                try:
                    texts = [c.content for c in child_chunks]
                    vectors = await self.provider.embed_batch(texts)
                    child_embeddings = [self.provider.validate_vector(v) for v in vectors]
                    embeddings_generated = True
                except Exception as emb_err:
                    logger.warning(
                        "Embedding generation failed for uploaded document %s, falling back to lexical-only: %s",
                        doc_id,
                        emb_err,
                    )
                    embeddings_generated = False
                    target_model = None

            # 6. Persist Parent and Child Chunks
            parent_id_map: Dict[int, uuid.UUID] = {}
            created_parents: List[DocumentChunk] = []
            created_children: List[DocumentChunk] = []

            for p_chunk in parent_chunks:
                p_id = uuid.uuid4()
                parent_id_map[p_chunk.chunk_index] = p_id
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
                    embedding=None,
                    embedding_model=None,
                    metadata_={
                        **p_chunk.metadata,
                        "doc_type": doc_type,
                        "file_name": safe_filename,
                        "page_number": p_chunk.metadata.get("page_number"),
                    },
                )
                self.session.add(db_parent)
                created_parents.append(db_parent)

            await self.session.flush()

            for c_idx, c_chunk in enumerate(child_chunks):
                parent_db_id = parent_id_map.get(c_chunk.parent_index) if c_chunk.parent_index is not None else None
                c_emb = child_embeddings[c_idx] if embeddings_generated and c_idx < len(child_embeddings) else None
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
                        "doc_type": doc_type,
                        "file_name": safe_filename,
                        "page_number": c_chunk.metadata.get("page_number"),
                        "parent_chunk_id": str(parent_db_id) if parent_db_id else None,
                    },
                )
                self.session.add(db_child)
                created_children.append(db_child)

            total_chunks = len(created_parents) + len(created_children)
            doc_obj.chunk_count = total_chunks
            doc_obj.processing_status = "processed"
            doc_obj.embedding_status = "embedded" if embeddings_generated else "lexical_only"
            doc_obj.error_message = None

            await self.session.commit()

            status_str = "completed"
            msg = (
                f"Successfully processed, chunked ({total_chunks} chunks), and embedded with {target_model}."
                if embeddings_generated
                else f"Successfully processed and chunked ({total_chunks} chunks). Lexical search indexed; semantic embeddings offline."
            )

            return IngestionResult(
                document_id=doc_id,
                title=effective_title,
                source_id=doc_obj.source_id,
                chunks_count=total_chunks,
                embeddings_generated=embeddings_generated,
                embedding_model=target_model,
                status=status_str,
                message=msg,
                document=doc_obj,
                chunks=created_parents + created_children,
                parent_chunks=created_parents,
                child_chunks=created_children,
            )

        except Exception as e:
            await self.session.rollback()
            if os.path.exists(storage_path):
                try:
                    os.remove(storage_path)
                except Exception:
                    pass
            logger.error("Failed to ingest user-uploaded document %s: %s", filename, e)
            raise
