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
from backend.app.schemas.investigation import PolicyCitation
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
        self.llm = llm_service or LLMReasoningService()
        self.retrieval = retrieval_service or HybridRetrievalService(session=session, llm_service=self.llm)
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
        """Synthesizes grounded answer using live LLM reasoning when available, verified against GroundingEngine."""
        # 1. Classify expected answer type (duration, amount, percentage, date, etc.)
        ans_type = "entity"
        if hasattr(self, "llm") and self.llm:
            try:
                ans_type = await self.llm.classify_expected_answer_type(query)
            except Exception as e:
                logger.debug("Answer type classification failed: %s", e)

        # 2. Stage 3 Deterministic candidate scoring
        det_answer, has_evidence, best_excerpt = self.grounding_engine.synthesize_grounded_answer(
            query=query,
            cited_excerpts=cited_excerpts,
            expected_answer_type=ans_type,
        )

        # 3. Stage 4 & 5: Live LLM Generation and Strict Multi-Tier Verification
        if hasattr(self, "llm") and self.llm and getattr(self.llm, "is_live_provider", False) and cited_excerpts:
            policy_citations = [
                PolicyCitation(
                    document_title=c.document_title,
                    section_header=c.section_title or "General",
                    excerpt=c.excerpt,
                    confidence_score=c.score,
                    document_id=c.document_id,
                    chunk_id=c.chunk_id,
                )
                for c in cited_excerpts[:5]
            ]
            try:
                structured_res = await self.llm.generate_structured_qa_answer(
                    query=query,
                    context_excerpts=policy_citations,
                )
                if structured_res and isinstance(structured_res, dict):
                    llm_ans = structured_res.get("answer", "").strip()
                    is_answerable = structured_res.get("answerable", True)

                    # If LLM abstained explicitly, fall back to verified deterministic ground truth if evidence is solid
                    if not is_answerable or "does not contain sufficient information" in llm_ans.lower():
                        logger.info("LLM determined question is unanswerable from context. Abstaining cleanly.")
                        return (
                            f"The provided document does not contain sufficient information to answer the question: '{query}'.",
                            False,
                            None,
                        )

                    # Stage 5 Verification Check 1: No bare headings
                    if not llm_ans.strip() or EvidenceGroundingEngine.is_bare_heading(llm_ans):
                        if has_evidence and best_excerpt:
                            return det_answer, True, best_excerpt
                        return (
                            f"The provided document does not contain sufficient information to answer the question: '{query}'.",
                            False,
                            None,
                        )

                    combined_evidence_text = "\n".join([c.excerpt for c in cited_excerpts[:5]])

                    # Stage 5 Verification Check 2: Number, Date, and Identifier Integrity
                    ans_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", llm_ans)
                    evidence_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", combined_evidence_text))
                    query_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", query))
                    allowed_numbers = evidence_numbers | query_numbers

                    # All numbers mentioned in the answer must appear in the evidence or query
                    unverified_numbers = [n for n in ans_numbers if n not in allowed_numbers]
                    if unverified_numbers:
                        logger.warning("LLM hallucinated unverified numbers %s. Falling back to deterministic answer.", unverified_numbers)
                        if has_evidence and best_excerpt:
                            return det_answer, True, best_excerpt
                        return (
                            f"The provided document does not contain sufficient information to answer the question: '{query}'.",
                            False,
                            None,
                        )

                    # Check alphanumeric rule IDs
                    ans_rule_ids = EvidenceGroundingEngine.extract_rule_ids(EvidenceGroundingEngine.tokenize_text(llm_ans))
                    evidence_rule_ids = EvidenceGroundingEngine.extract_rule_ids(EvidenceGroundingEngine.tokenize_text(combined_evidence_text))
                    unverified_rule_ids = [r for r in ans_rule_ids if r not in evidence_rule_ids]
                    if unverified_rule_ids:
                        logger.warning("LLM hallucinated unverified rule IDs %s. Falling back to deterministic answer.", unverified_rule_ids)
                        if has_evidence and best_excerpt:
                            return det_answer, True, best_excerpt
                        return (
                            f"The provided document does not contain sufficient information to answer the question: '{query}'.",
                            False,
                            None,
                        )

                    # Stage 5 Verification Check 3: Adversarial currency & topic constraint checks
                    query_tokens = EvidenceGroundingEngine.tokenize_text(query.lower())
                    query_currencies = {
                        c for c, terms in self.grounding_engine.registry.CURRENCIES.items()
                        if any(t in query_tokens for t in terms)
                    }
                    evidence_tokens = EvidenceGroundingEngine.tokenize_text(combined_evidence_text.lower())
                    if query_currencies:
                        evidence_currencies = {
                            c for c, terms in self.grounding_engine.registry.CURRENCIES.items()
                            if any(t in evidence_tokens for t in terms)
                        }
                        if evidence_currencies and not (query_currencies & evidence_currencies):
                            logger.info("Adversarial currency mismatch detected: query asked %s, evidence has %s", query_currencies, evidence_currencies)
                            return (
                                f"The provided document does not contain sufficient information to answer the question: '{query}'.",
                                False,
                                None,
                            )

                    query_rails = {
                        r for r, terms in self.grounding_engine.registry.PAYMENT_RAILS.items()
                        if any(t in query_tokens for t in terms)
                    }
                    if "crypto" in query_rails:
                        evidence_rails = {
                            r for r, terms in self.grounding_engine.registry.PAYMENT_RAILS.items()
                            if any(t in evidence_tokens for t in terms)
                        }
                        if "crypto" not in evidence_rails:
                            logger.info("Adversarial crypto rail mismatch: query asked crypto, evidence lacks crypto")
                            return (
                                f"The provided document does not contain sufficient information to answer the question: '{query}'.",
                                False,
                                None,
                            )

                    # Stage 5 Verification Check 4: Entailment reasoning against combined evidence
                    entailed = await self.llm.verify_entailment(combined_evidence_text, llm_ans)
                    if not entailed:
                        logger.warning("LLM answer failed entailment check. Falling back to deterministic answer.")
                        if has_evidence and best_excerpt:
                            return det_answer, True, best_excerpt
                        return (
                            f"The provided document does not contain sufficient information to answer the question: '{query}'.",
                            False,
                            None,
                        )

                    # All verification checks passed!
                    chosen_excerpt = best_excerpt or cited_excerpts[0]
                    return llm_ans, True, chosen_excerpt
            except Exception as exc:
                logger.warning("LLM QA generation failed (%s). Using verified deterministic answer.", exc)

        # 4. Deterministic verified answer fallback (for tests without live LLM)
        if has_evidence and best_excerpt:
            return det_answer, True, best_excerpt

        return (
            f"The provided document does not contain sufficient information to answer the question: '{query}'.",
            False,
            None,
        )
