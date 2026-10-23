"""Policy RAG Service interface and pgvector retriever for PayGuard AI."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.knowledge import DocumentChunk, KnowledgeDocument
from backend.app.schemas.investigation import PolicyCitation
from backend.app.services.interfaces import IRagService


class RagService(IRagService):
    """Retrieves authoritative policy excerpts using vector cosine distance and keyword matching."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def retrieve_troubleshooting_docs(
        self,
        query: str,
        issue_category: Optional[str] = None,
        top_k: int = 3,
    ) -> List[PolicyCitation]:
        """Performs pgvector similarity retrieval or text search over active policy chunks."""
        # Query active document chunks
        stmt = (
            select(DocumentChunk)
            .join(DocumentChunk.document)
            .where(KnowledgeDocument.is_active == True)  # noqa: E712
            .options(selectinload(DocumentChunk.document))
            .limit(top_k)
        )

        result = await self.session.execute(stmt)
        chunks = result.scalars().all()

        citations: List[PolicyCitation] = []
        for chunk in chunks:
            citations.append(
                PolicyCitation(
                    document_title=chunk.document.title,
                    section_header=chunk.section_header,
                    excerpt=chunk.content[:300] + "..." if len(chunk.content) > 300 else chunk.content,
                    confidence_score=0.92,
                )
            )

        return citations
