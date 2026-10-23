"""Knowledge document and chunk repository operations for compliance and policy docs."""

from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.knowledge import DocumentChunk, KnowledgeDocument


class KnowledgeService:
    """Manages knowledge documents and their chunked text passages."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_document(
        self,
        title: str,
        doc_type: str,
        version: str,
        source_url: Optional[str] = None,
        is_active: bool = True,
    ) -> KnowledgeDocument:
        doc = KnowledgeDocument(
            id=uuid.uuid4(),
            title=title,
            doc_type=doc_type,
            version=version,
            source_url=source_url,
            is_active=is_active,
        )
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def get_document_by_id(self, doc_id: uuid.UUID) -> Optional[KnowledgeDocument]:
        stmt = (
            select(KnowledgeDocument)
            .where(KnowledgeDocument.id == doc_id)
            .options(selectinload(KnowledgeDocument.chunks))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_document_by_title(self, title: str) -> Optional[KnowledgeDocument]:
        stmt = (
            select(KnowledgeDocument)
            .where(KnowledgeDocument.title == title)
            .options(selectinload(KnowledgeDocument.chunks))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_documents(self, doc_type: Optional[str] = None) -> List[KnowledgeDocument]:
        stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.title)
        if doc_type:
            stmt = stmt.where(KnowledgeDocument.doc_type == doc_type)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_chunk(
        self,
        document_id: uuid.UUID,
        chunk_index: int,
        section_header: str,
        content: str,
        token_count: int,
        embedding: Optional[List[float]] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> DocumentChunk:
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=document_id,
            chunk_index=chunk_index,
            section_header=section_header,
            content=content,
            token_count=token_count,
            embedding=embedding,
            metadata_=metadata_ or {},
        )
        self.session.add(chunk)
        await self.session.commit()
        await self.session.refresh(chunk)
        return chunk
