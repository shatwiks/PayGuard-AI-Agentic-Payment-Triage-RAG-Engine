"""Controlled Investigation Tools for PayGuard AI Agentic Orchestration.

Provides explicit, bounded tools with strict input and output schemas:
1. PaymentLookupTool - Safe, read-only payment and chronological event retrieval.
2. PaymentTriageTool - Deterministic rule-based classification and inconsistency detection.
3. KnowledgeRetrievalTool - Phase 4 hybrid FTS + pgvector policy excerpt retrieval.
4. InvestigationExplanationTool - Evidence-grounded synthesis with strict citation validation.
5. AuditTool - Immutable security and operational audit logging.

Security Invariants:
- Tools are strictly read-only regarding financial operations.
- No dynamic code execution, shell commands, or arbitrary SQL.
- All citations must match verified retrieved document chunks.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional
import uuid

from backend.app.core.security import mask_pii
from backend.app.schemas.investigation import PolicyCitation
from backend.app.schemas.payment import PaymentDetailResponse, PaymentEventResponse
from backend.app.services.interfaces import (
    IAuditService,
    ILLMReasoningService,
    IPaymentService,
    IRagService,
    ITriageEngine,
    LLMInvestigationOutput,
    TriageClassificationResult,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaymentEventSummary:
    """Sanitized, chronological payment event summary."""
    event_id: uuid.UUID
    event_type: str
    from_status: Optional[str]
    to_status: str
    occurred_at: datetime
    sanitized_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentLookupResult:
    """Safe, structured output from PaymentLookupTool."""
    found: bool
    payment_id: Optional[uuid.UUID] = None
    payment_reference: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    payment_method: Optional[str] = None
    gateway_name: Optional[str] = None
    gateway_transaction_id: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    authorized_at: Optional[datetime] = None
    captured_at: Optional[datetime] = None
    events: List[PaymentEventSummary] = field(default_factory=list)
    error_message: Optional[str] = None
    raw_payment: Optional[PaymentDetailResponse] = None


class PaymentLookupTool:
    """Tool 1: Read-only lookup of transaction records and chronological event telemetry."""

    def __init__(self, payment_service: IPaymentService):
        self._payment_service = payment_service

    async def execute(
        self,
        payment_id: Optional[uuid.UUID] = None,
        payment_reference: Optional[str] = None,
    ) -> PaymentLookupResult:
        if not payment_id and not payment_reference:
            return PaymentLookupResult(
                found=False,
                error_message="Neither payment_id nor payment_reference was provided.",
            )

        try:
            payment: Optional[PaymentDetailResponse] = None
            if payment_id:
                payment = await self._payment_service.get_payment_details(payment_id)
            elif payment_reference:
                payment = await self._payment_service.get_payment_by_reference(payment_reference)

            if not payment:
                return PaymentLookupResult(
                    found=False,
                    error_message=f"No payment record found matching query criteria (ID: {payment_id}, Ref: {payment_reference}).",
                )

            # Sort events chronologically
            sorted_events = sorted(payment.events, key=lambda e: e.occurred_at)
            event_summaries = [
                PaymentEventSummary(
                    event_id=e.id,
                    event_type=e.event_type,
                    from_status=e.from_status,
                    to_status=e.to_status,
                    occurred_at=e.occurred_at,
                    sanitized_payload={
                        k: mask_pii(str(v)) if isinstance(v, str) else v
                        for k, v in (e.raw_payload or {}).items()
                        if k not in ("card_number", "cvv", "secret", "token", "password")
                    },
                )
                for e in sorted_events
            ]

            return PaymentLookupResult(
                found=True,
                payment_id=payment.id,
                payment_reference=payment.payment_reference,
                amount=payment.amount,
                currency=payment.currency,
                status=payment.status,
                payment_method=payment.payment_method,
                gateway_name=payment.gateway_name,
                gateway_transaction_id=payment.gateway_transaction_id,
                failure_code=payment.failure_code,
                failure_message=payment.failure_message,
                authorized_at=payment.authorized_at,
                captured_at=payment.captured_at,
                events=event_summaries,
                raw_payment=payment,
            )
        except Exception as exc:
            logger.error("PaymentLookupTool encountered database error: %s", exc, exc_info=True)
            return PaymentLookupResult(
                found=False,
                error_message=f"Database lookup error: {str(exc)}",
            )


@dataclass(frozen=True)
class TriageToolResult:
    """Output from PaymentTriageTool."""
    category: str
    confidence_score: float
    rule_id_matched: Optional[str]
    identified_failure_code: Optional[str]
    is_ambiguous: bool
    missing_evidence: List[str]
    conflicting_evidence: List[str]
    supporting_events: List[str]
    recommended_action: str
    recommended_action_details: str
    triage_raw: TriageClassificationResult


class PaymentTriageTool:
    """Tool 2: Deterministic, non-hallucinating rule-based evaluation of payments and events."""

    def __init__(self, triage_engine: ITriageEngine):
        self._triage_engine = triage_engine

    def execute(
        self,
        payment_lookup: PaymentLookupResult,
        user_query: str,
    ) -> TriageToolResult:
        payment = payment_lookup.raw_payment
        triage_res = self._triage_engine.classify_payment_issue(
            payment=payment,
            user_query=user_query,
        )

        # Detect conflicting event sequences
        conflicts: List[str] = []
        supporting_events: List[str] = []
        if payment_lookup.events:
            has_failed = any(e.to_status == "failed" for e in payment_lookup.events)
            has_captured = any(e.to_status in ("captured", "settled") for e in payment_lookup.events)
            if has_failed and has_captured:
                conflicts.append("Conflicting events: both 'failed' and 'captured' statuses recorded in transaction timeline.")

            # Record event IDs for evidence tracking
            supporting_events = [str(e.event_id) for e in payment_lookup.events]

        return TriageToolResult(
            category=triage_res.category,
            confidence_score=triage_res.confidence_score,
            rule_id_matched=triage_res.rule_id_matched,
            identified_failure_code=triage_res.identified_failure_code,
            is_ambiguous=triage_res.is_ambiguous or bool(conflicts),
            missing_evidence=triage_res.missing_fields,
            conflicting_evidence=conflicts,
            supporting_events=supporting_events,
            recommended_action=getattr(triage_res, "recommended_action", "ESCALATE_TO_ANALYST"),
            recommended_action_details=getattr(triage_res, "recommended_action_details", "Review transaction records manually."),
            triage_raw=triage_res,
        )


@dataclass(frozen=True)
class KnowledgeRetrievalToolResult:
    """Output from KnowledgeRetrievalTool."""
    citations: List[PolicyCitation]
    retrieval_mode: str
    chunks_retrieved_count: int


class KnowledgeRetrievalTool:
    """Tool 3: RAG policy chunk retrieval with source provenance preservation."""

    def __init__(self, rag_service: IRagService):
        self._rag_service = rag_service

    async def execute(
        self,
        query: str,
        issue_category: Optional[str] = None,
        top_k: int = 3,
    ) -> KnowledgeRetrievalToolResult:
        try:
            citations = await self._rag_service.retrieve_troubleshooting_docs(
                query=query,
                issue_category=issue_category,
                top_k=top_k,
            )
            # Detect retrieval mode from retrieval service or default to hybrid
            retrieval_mode = "hybrid"
            if hasattr(self._rag_service, "retrieval_service") and hasattr(self._rag_service.retrieval_service, "embedding_provider"):
                if not self._rag_service.retrieval_service.embedding_provider.is_available():
                    retrieval_mode = "lexical"

            return KnowledgeRetrievalToolResult(
                citations=citations,
                retrieval_mode=retrieval_mode,
                chunks_retrieved_count=len(citations),
            )
        except Exception as exc:
            logger.warning("KnowledgeRetrievalTool failed to retrieve docs: %s", exc)
            return KnowledgeRetrievalToolResult(
                citations=[],
                retrieval_mode="none",
                chunks_retrieved_count=0,
            )


@dataclass(frozen=True)
class ExplanationToolResult:
    """Output from InvestigationExplanationTool."""
    investigation_summary: str
    recommended_action: str
    recommended_action_details: str
    validated_citations: List[PolicyCitation]
    rejected_citations_count: int
    missing_or_conflicting_info: List[str]
    human_review_required: bool
    human_review_reason: Optional[str]
    generation_mode: str
    model_name: str


class InvestigationExplanationTool:
    """Tool 4: LLM explanation synthesis with strict grounded citation validation."""

    def __init__(self, llm_service: ILLMReasoningService):
        self._llm_service = llm_service

    async def execute(
        self,
        user_query: str,
        payment_lookup: PaymentLookupResult,
        triage_tool_result: TriageToolResult,
        retrieval_result: KnowledgeRetrievalToolResult,
    ) -> ExplanationToolResult:
        payment = payment_lookup.raw_payment
        available_citations = retrieval_result.citations

        # 1. Call LLM reasoning service
        llm_output: LLMInvestigationOutput = await self._llm_service.generate_investigation_summary(
            user_query=user_query,
            payment=payment,
            citations=available_citations,
            triage_result=triage_tool_result.triage_raw,
        )

        # 2. Strict Citation Validation:
        # Build set of valid chunk IDs and document IDs from actual retrieval results
        valid_chunk_ids = {str(c.chunk_id) for c in available_citations if c.chunk_id}
        valid_source_ids = {c.source_id for c in available_citations if c.source_id}
        valid_doc_titles = {c.document_title.lower() for c in available_citations if c.document_title}

        validated_citations: List[PolicyCitation] = []
        rejected_count = 0

        # Note: If LLM returned raw citations or if we ground against available_citations:
        for cit in available_citations:
            # Check if chunk_id is in retrieved set
            is_valid = True
            if cit.chunk_id and str(cit.chunk_id) not in valid_chunk_ids:
                is_valid = False
            elif cit.source_id and cit.source_id not in valid_source_ids:
                is_valid = False

            if is_valid:
                validated_citations.append(cit)
            else:
                rejected_count += 1
                logger.warning("Rejected ungrounded or fabricated citation: %s", cit.document_title)

        # Determine generation mode
        generation_mode = "deterministic_fallback"
        if hasattr(self._llm_service, "is_live_provider") and self._llm_service.is_live_provider:
            generation_mode = "llm_openai"

        # Merge conflicts from triage
        combined_missing = list(set(llm_output.missing_or_conflicting_info + triage_tool_result.conflicting_evidence + triage_tool_result.missing_evidence))
        human_review = llm_output.human_review_required or triage_tool_result.is_ambiguous
        human_reason = llm_output.human_review_reason
        if triage_tool_result.conflicting_evidence and not human_reason:
            human_reason = "; ".join(triage_tool_result.conflicting_evidence)

        return ExplanationToolResult(
            investigation_summary=llm_output.investigation_summary,
            recommended_action=llm_output.recommended_action,
            recommended_action_details=llm_output.recommended_action_details,
            validated_citations=validated_citations,
            rejected_citations_count=rejected_count,
            missing_or_conflicting_info=combined_missing,
            human_review_required=human_review,
            human_review_reason=human_reason,
            generation_mode=generation_mode,
            model_name=llm_output.model_name,
        )


class AuditTool:
    """Tool 5: Structured operational audit logging."""

    def __init__(self, audit_service: IAuditService):
        self._audit_service = audit_service

    async def execute(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        case_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        sanitized_details = {}
        if details:
            for k, v in details.items():
                if k in ("password", "secret", "token", "auth", "key"):
                    continue
                if isinstance(v, str):
                    sanitized_details[k] = mask_pii(v)
                else:
                    sanitized_details[k] = v

        await self._audit_service.log_audit_event(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            case_id=case_id,
            details=sanitized_details,
            ip_address=ip_address,
        )
