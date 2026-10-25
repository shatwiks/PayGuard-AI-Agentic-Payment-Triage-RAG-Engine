"""Document-grounded question answering service for PayGuard AI.

Provides:
1. Strict scope and document-level authorization enforcement (multi-tenant isolation).
2. Retrieval of relevant hierarchical child chunks with parent context.
3. Grounded answer generation using verified document excerpts via EvidenceGroundingEngine.
4. Clean abstention when requested facts are absent from the document.
5. Exact citation attribution (document title, section, page number, chunk ID).
6. Deterministic grounded fallback when live LLM provider is offline.
"""

import logging
import re
from typing import List, Optional, Set, Tuple
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import NotFoundException, UnauthorizedException
from backend.app.models.knowledge import KnowledgeDocument
from backend.app.models.user import User
from backend.app.schemas.knowledge import (
    CitedExcerptItem,
    DocumentAskRequest,
    DocumentAskResponse,
)
from backend.app.services.grounding import EvidenceGroundingEngine, FinancialConstraintRegistry
from backend.app.services.llm import LLMReasoningService
from backend.app.services.retrieval import HybridRetrievalService

logger = logging.getLogger("payguard.document_qa")


class DocumentQAService:
    """Answers user questions strictly grounded in authorized uploaded or system documents."""

    _default_grounding_engine = EvidenceGroundingEngine()

    def __init__(
        self,
        session: AsyncSession,
        retrieval_service: Optional[HybridRetrievalService] = None,
        llm_service: Optional[LLMReasoningService] = None,
        grounding_engine: Optional[EvidenceGroundingEngine] = None,
    ):
        self.session = session
        self.retrieval = retrieval_service or HybridRetrievalService(session=session)
        self.llm = llm_service or LLMReasoningService()
        self.grounding_engine = grounding_engine or EvidenceGroundingEngine()

    @property
    def retrieval_service(self) -> HybridRetrievalService:
        """Alias for self.retrieval."""
        return self.retrieval

    async def _verify_and_resolve_scope(
        self,
        user: User,
        document_ids: Optional[List[uuid.UUID]],
        scope: str,
    ) -> List[uuid.UUID]:
        """Validates user authorization for requested document scope and returns allowed document UUIDs."""
        if document_ids:
            # Explicit document IDs requested: verify ownership or system flag for every ID
            stmt = select(KnowledgeDocument).where(
                KnowledgeDocument.id.in_(document_ids),
                KnowledgeDocument.is_active.is_(True),
            )
            res = await self.session.execute(stmt)
            found_docs = res.scalars().all()

            found_map = {d.id: d for d in found_docs}
            for req_id in document_ids:
                if req_id not in found_map:
                    raise NotFoundException(f"Document with ID '{req_id}' not found.")
                doc = found_map[req_id]
                # Non-admin users can only view system documents or their own uploaded documents
                if not doc.is_system and doc.uploaded_by_id != user.id and user.role != "admin":
                    raise NotFoundException(f"Document with ID '{req_id}' not found.")

            return [d.id for d in found_docs]

        # Scope-based resolution
        stmt = select(KnowledgeDocument.id).where(KnowledgeDocument.is_active.is_(True))
        if scope == "uploaded":
            # Only user's uploaded documents
            stmt = stmt.where(
                KnowledgeDocument.uploaded_by_id == user.id,
                KnowledgeDocument.is_system.is_(False),
            )
        elif scope == "knowledge_base":
            # Only authoritative system documents
            stmt = stmt.where(KnowledgeDocument.is_system.is_(True))
        else:
            # "all": System documents + user's uploaded documents
            stmt = stmt.where(
                or_(
                    KnowledgeDocument.is_system.is_(True),
                    KnowledgeDocument.uploaded_by_id == user.id,
                )
            )

        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def ask_question(
        self,
        user: User,
        request: DocumentAskRequest,
    ) -> DocumentAskResponse:
        """Answers a question strictly using evidence from the user's authorized document scope."""
        authorized_doc_ids = await self._verify_and_resolve_scope(
            user=user,
            document_ids=request.document_ids,
            scope=request.scope,
        )

        if not authorized_doc_ids:
            return DocumentAskResponse(
                query=request.query,
                answer="No documents are available in the selected scope to answer this question.",
                has_sufficient_evidence=False,
                cited_excerpts=[],
                retrieval_mode_used="none",
                embedding_status="none",
                scope_used=request.scope,
            )

        # Retrieve relevant chunks within authorized document scope
        search_res = await self.retrieval.search(
            query=request.query,
            top_k=request.top_k,
            retrieval_mode=request.retrieval_mode,
            document_ids=authorized_doc_ids,
            user_id=user.id,
            scope=request.scope,
            user_role=user.role,
            include_parent_context=True,
        )

        cited_excerpts: List[CitedExcerptItem] = []
        for r in search_res.results:
            page_num = r.page_number or (r.metadata.get("page_number") if isinstance(r.metadata, dict) else None)
            score = r.ranking.fusion_score if (hasattr(r, "ranking") and r.ranking) else 0.0

            cited_excerpts.append(
                CitedExcerptItem(
                    document_id=r.document_id,
                    document_title=r.title,
                    chunk_id=r.chunk_id,
                    section_title=r.section_title or r.section_header,
                    page_number=page_num,
                    excerpt=r.content,
                    parent_excerpt=getattr(r, "parent_content", None),
                    score=score,
                )
            )

        active_embedding = "embedded" if any(getattr(r, "embedding_model", None) for r in search_res.results) else "lexical_only"

        if not cited_excerpts:
            return DocumentAskResponse(
                query=request.query,
                answer=f"The provided document does not contain sufficient information to answer the question: '{request.query}'.",
                has_sufficient_evidence=False,
                cited_excerpts=[],
                retrieval_mode_used=search_res.retrieval_mode,
                embedding_status=active_embedding,
                scope_used=request.scope,
            )

        # Grounded answer synthesis (Live LLM or Deterministic Grounded Engine)
        answer, has_evidence, best_excerpt = await self._synthesize_grounded_answer(
            query=request.query,
            cited_excerpts=cited_excerpts,
        )

        ordered_excerpts = []
        if has_evidence and best_excerpt:
            ordered_excerpts = [best_excerpt] + [c for c in cited_excerpts if c.chunk_id != best_excerpt.chunk_id]
        elif has_evidence:
            ordered_excerpts = cited_excerpts

        citations = [
            {
                "document_id": str(c.document_id),
                "document_name": c.document_title,
                "chunk_id": str(c.chunk_id) if c.chunk_id else "",
                "section": c.section_title or "General",
                "page": c.page_number,
                "excerpt": c.excerpt,
            }
            for c in ordered_excerpts
        ] if has_evidence else []

        return DocumentAskResponse(
            query=request.query,
            answer=answer,
            has_sufficient_evidence=has_evidence,
            is_grounded=has_evidence,
            cited_excerpts=ordered_excerpts if has_evidence else [],
            citations=citations,
            retrieval_mode_used=search_res.retrieval_mode,
            embedding_status=active_embedding,
            scope_used=request.scope,
        )

    # Class-level backward-compatible delegates to FinancialConstraintRegistry
    _STOPWORDS = FinancialConstraintRegistry.STOPWORDS
    _META_WORDS = FinancialConstraintRegistry.META_WORDS
    _GENERIC_ATTRIBUTES = FinancialConstraintRegistry.GENERIC_ATTRIBUTES
    _CURRENCIES = FinancialConstraintRegistry.CURRENCIES
    _TOPIC_CONSTRAINTS = FinancialConstraintRegistry.TOPIC_CONSTRAINTS
    _PAYMENT_RAILS = FinancialConstraintRegistry.PAYMENT_RAILS
    _MODIFIER_PAIRS = FinancialConstraintRegistry.MODIFIER_PAIRS
    _TIME_UNITS = FinancialConstraintRegistry.TIME_UNITS
    _SYNONYM_CLUSTERS = FinancialConstraintRegistry.SYNONYM_CLUSTERS

    # Class-level backward-compatible helper delegates to EvidenceGroundingEngine
    _stem = staticmethod(EvidenceGroundingEngine.stem)
    _tokenize_text = classmethod(lambda cls, text: EvidenceGroundingEngine.tokenize_text(text))
    _extract_rule_ids = classmethod(lambda cls, tokens: EvidenceGroundingEngine.extract_rule_ids(tokens))

    @classmethod
    def _terms_match(cls, q_term: str, doc_tokens: Set[str], context_text: str) -> bool:
        return cls._default_grounding_engine.terms_match(q_term, doc_tokens, context_text)

    async def _synthesize_grounded_answer(
        self,
        query: str,
        cited_excerpts: List[CitedExcerptItem],
    ) -> Tuple[str, bool, Optional[CitedExcerptItem]]:
        """Synthesizes grounded answer using the dedicated EvidenceGroundingEngine."""
        return self.grounding_engine.synthesize_grounded_answer(
            query=query,
            cited_excerpts=cited_excerpts,
        )
