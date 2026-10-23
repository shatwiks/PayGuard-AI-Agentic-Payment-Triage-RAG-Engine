"""Policy RAG Service interface and pgvector retriever for PayGuard AI."""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.schemas.investigation import PolicyCitation
from backend.app.schemas.knowledge import KnowledgeSearchRequest
from backend.app.services.interfaces import IRagService
from backend.app.services.retrieval import HybridRetrievalService


class RagService(IRagService):
    """Retrieves authoritative policy excerpts using hybrid FTS + pgvector search and grounded citations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.retrieval_service = HybridRetrievalService(session=session)

    async def retrieve_troubleshooting_docs(
        self,
        query: str,
        issue_category: Optional[str] = None,
        top_k: int = 3,
    ) -> List[PolicyCitation]:
        """Performs hybrid retrieval combining PostgreSQL full-text search and pgvector similarity."""
        req = KnowledgeSearchRequest(
            query=query,
            top_k=top_k,
            retrieval_mode="hybrid",
        )
        response = await self.retrieval_service.search(req)
        return self.retrieval_service.to_citations(response.results)
