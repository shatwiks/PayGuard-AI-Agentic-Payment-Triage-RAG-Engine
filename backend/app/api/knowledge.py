"""Knowledge base retrieval and search API router."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.user import User
from backend.app.schemas.knowledge import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
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
) -> KnowledgeSearchResponse:
    """Executes hybrid, lexical-only, or semantic-only search over indexed policy chunks."""
    retrieval_service = HybridRetrievalService(session=db)
    return await retrieval_service.search(request)
