"""Knowledge base retrieval and search API router."""

import hashlib
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.rate_limit import rate_limit
from backend.app.core.security import get_current_user, require_role
from backend.app.models.user import User
from backend.app.schemas.knowledge import (
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from backend.app.services.ingestion import DocumentIngestionPipeline
from backend.app.services.retrieval import HybridRetrievalService

router = APIRouter(prefix="/knowledge", tags=["Knowledge & Policies"])


@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Hybrid Knowledge Search",
    description="Searches authoritative payment policies using combined lexical full-text and pgvector semantic retrieval.",
)
async def search_knowledge_documents(
    request: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rate_guard: None = Depends(rate_limit("knowledge_search", max_requests=settings.RATE_LIMIT_SEARCH_PER_MINUTE)),
) -> KnowledgeSearchResponse:
    """Executes hybrid, lexical-only, or semantic-only search over indexed policy chunks."""
    retrieval_service = HybridRetrievalService(session=db)
    return await retrieval_service.search(request)


@router.post(
    "/ingest",
    response_model=KnowledgeIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest Policy Document",
    description="Admin/Compliance restricted endpoint to ingest, normalize, chunk, and embed official payment policies.",
)
async def ingest_policy_document(
    request: KnowledgeIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "compliance_analyst"])),
    _rate_guard: None = Depends(rate_limit("knowledge_ingest", max_requests=10)),
) -> KnowledgeIngestResponse:
    """Ingests official document and persists normalized chunks with embeddings."""
    pipeline = DocumentIngestionPipeline(session=db)
    result = await pipeline.ingest_document(
        title=request.title,
        content=request.raw_content,
        source_id=request.source_id,
        doc_type=request.document_type,
        version=request.version,
        source_url=request.source_url,
    )
    content_hash = (
        result.document.content_hash
        if result.document
        else hashlib.sha256(request.raw_content.encode("utf-8")).hexdigest()
    )
    return KnowledgeIngestResponse(
        document_id=result.document_id,
        source_id=result.source_id,
        title=result.title,
        chunks_created=result.chunks_count,
        content_hash=content_hash,
        status="ingested",
    )
