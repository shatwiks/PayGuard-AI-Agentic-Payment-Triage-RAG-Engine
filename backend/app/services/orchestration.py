"""Investigation Orchestration Service coordinating the agentic payment triage pipeline.

Executes the 11 explicit investigation lifecycle stages:
1. Validate & sanitize PII in request query.
2. Lookup payment and chronological events via PaymentLookupTool.
3. Execute deterministic triage classification via PaymentTriageTool.
4. Retrieve authoritative policy documents via KnowledgeRetrievalTool.
5. Construct a structured, immutable evidence package.
6. Generate grounded synthesis via InvestigationExplanationTool.
7. Validate explanation and strictly ground citations against retrieved chunks.
8. Persist InvestigationCase & InvestigationResult with transactional atomicity.
9. Record audit event via AuditTool.
10. Reload and return strongly typed InvestigationCaseResponse.
"""

from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Any, Dict, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.core.security import mask_pii, sanitize_prompt_input
from backend.app.models.investigation import InvestigationCase, InvestigationResult
from backend.app.schemas.auth import UserResponse
from backend.app.schemas.investigation import (
    InvestigationCaseResponse,
    InvestigationCreateRequest,
)
from backend.app.services.interfaces import (
    IAuditService,
    ILLMReasoningService,
    IOrchestrationService,
    IPaymentService,
    IRagService,
    ITriageEngine,
)
from backend.app.services.tools import (
    AuditTool,
    InvestigationExplanationTool,
    KnowledgeRetrievalTool,
    PaymentLookupTool,
    PaymentTriageTool,
    ToolRegistry,
)

logger = logging.getLogger(__name__)


class OrchestrationService(IOrchestrationService):
    """End-to-end payment dispute triage orchestrator.
    Coordinates controlled investigation tools to ensure grounded, verifiable resolutions.
    """

    def __init__(
        self,
        session: AsyncSession,
        payment_service: IPaymentService,
        triage_engine: ITriageEngine,
        rag_service: IRagService,
        llm_service: ILLMReasoningService,
        audit_service: IAuditService,
    ):
        self.session = session
        self.payment_service = payment_service
        self.triage_engine = triage_engine
        self.rag_service = rag_service
        self.llm_service = llm_service
        self.audit_service = audit_service

        # Instantiate bounded investigation tools
        self.payment_lookup_tool = PaymentLookupTool(payment_service)
        self.triage_tool = PaymentTriageTool(triage_engine)
        self.retrieval_tool = KnowledgeRetrievalTool(rag_service)
        self.explanation_tool = InvestigationExplanationTool(llm_service)
        self.audit_tool = AuditTool(audit_service)

        # Explicit tool registry enforcing whitelisted tool access
        self.tool_registry = ToolRegistry(
            payment_lookup=self.payment_lookup_tool,
            payment_triage=self.triage_tool,
            knowledge_retrieval=self.retrieval_tool,
            explanation=self.explanation_tool,
            audit=self.audit_tool,
        )

    async def run_investigation(
        self,
        request: InvestigationCreateRequest,
        current_user: Optional[UserResponse] = None,
    ) -> InvestigationCaseResponse:
        start_time = time.perf_counter()

        # Idempotency Check: prevent duplicate writes on quick retries
        if request.payment_id or request.payment_reference:
            cutoff = datetime.now(timezone.utc) - timedelta(
                seconds=settings.INVESTIGATION_IDEMPOTENCY_WINDOW_SECONDS
            )
            idempotency_conditions = [
                InvestigationCase.customer_query == request.customer_query,
                InvestigationCase.created_at >= cutoff,
            ]
            if request.payment_id:
                idempotency_conditions.append(InvestigationCase.payment_id == request.payment_id)

            existing_stmt = (
                select(InvestigationCase)
                .where(*idempotency_conditions)
                .options(
                    selectinload(InvestigationCase.payment),
                    selectinload(InvestigationCase.result),
                )
                .order_by(InvestigationCase.created_at.desc())
                .limit(1)
            )
            existing_res = await self.session.execute(existing_stmt)
            existing_case = existing_res.scalar_one_or_none()
            if existing_case:
                logger.info(
                    "Idempotency hit: returning existing recent case %s for query",
                    existing_case.id,
                )
                return InvestigationCaseResponse.model_validate(existing_case)

        # Stage 1: Validate and mask PII in customer query
        sanitized_query = mask_pii(request.customer_query)
        clean_query, injection_detected = sanitize_prompt_input(sanitized_query)
        if injection_detected:
            logger.warning("Prompt injection pattern detected and neutralized in customer query.")
            sanitized_query = clean_query

        # Stage 2: Retrieve payment and chronological event history via verified tool
        self.tool_registry.validate_tool_name("payment_lookup")
        payment_lookup = await self.payment_lookup_tool.execute(
            payment_id=request.payment_id,
            payment_reference=request.payment_reference,
        )

        # Stage 3: Deterministic payment triage evaluation
        self.tool_registry.validate_tool_name("payment_triage")
        triage_result = self.triage_tool.execute(
            payment_lookup=payment_lookup,
            user_query=sanitized_query,
        )

        # Stage 4: Retrieve relevant policy and troubleshooting documents via hybrid RAG
        self.tool_registry.validate_tool_name("knowledge_retrieval")
        retrieval_result = await self.retrieval_tool.execute(
            query=sanitized_query,
            issue_category=triage_result.category,
            top_k=3,
        )


        # Stage 5: Construct structured, verified evidence package
        evidence_package: Dict[str, Any] = {
            "payment_id": str(payment_lookup.payment_id) if payment_lookup.payment_id else None,
            "payment_reference": payment_lookup.payment_reference,
            "payment_status": payment_lookup.status,
            "amount": str(payment_lookup.amount) if payment_lookup.amount else None,
            "currency": payment_lookup.currency,
            "gateway_name": payment_lookup.gateway_name,
            "failure_code": payment_lookup.failure_code,
            "events_count": len(payment_lookup.events),
            "chronological_event_ids": triage_result.supporting_events,
            "triage_category": triage_result.category,
            "triage_rule_matched": triage_result.rule_id_matched,
            "triage_confidence": triage_result.confidence_score,
            "conflicts_detected": triage_result.conflicting_evidence,
            "missing_evidence": triage_result.missing_evidence,
            "retrieval_mode": retrieval_result.retrieval_mode,
            "retrieved_chunks_count": retrieval_result.chunks_retrieved_count,
        }

        # Stage 6 & 7: Generate grounded synthesis and strictly validate citations
        explanation_result = await self.explanation_tool.execute(
            user_query=sanitized_query,
            payment_lookup=payment_lookup,
            triage_tool_result=triage_result,
            retrieval_result=retrieval_result,
        )

        execution_time_ms = int((time.perf_counter() - start_time) * 1000)

        # Stage 8: Persist InvestigationCase & InvestigationResult atomically
        case_id = uuid.uuid4()
        case_number = f"CASE-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(case_id)[:8].upper()}"

        db_case = InvestigationCase(
            id=case_id,
            case_number=case_number,
            payment_id=payment_lookup.payment_id if payment_lookup.found else None,
            created_by_user_id=current_user.id if current_user else None,
            customer_query=request.customer_query,
            sanitized_query=sanitized_query,
            status="triaged",
            priority=request.priority or "medium",
        )

        validated_citations_data = [c.model_dump(mode="json") for c in explanation_result.validated_citations]


        db_result = InvestigationResult(
            id=uuid.uuid4(),
            case_id=case_id,
            issue_category=triage_result.category,
            confidence_score=triage_result.confidence_score,
            investigation_summary=explanation_result.investigation_summary,
            recommended_action=explanation_result.recommended_action,
            recommended_action_details=explanation_result.recommended_action_details,
            policy_citations=validated_citations_data,
            missing_or_conflicting_info=explanation_result.missing_or_conflicting_info,
            human_review_required=explanation_result.human_review_required,
            human_review_reason=explanation_result.human_review_reason,
            execution_time_ms=execution_time_ms,
            llm_model_name=explanation_result.model_name,
            retrieval_mode=retrieval_result.retrieval_mode,
            generation_mode=explanation_result.generation_mode,
            evidence_package=evidence_package,
        )

        try:
            self.session.add(db_case)
            self.session.add(db_result)
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            logger.error("Failed to persist investigation case %s: %s", case_id, exc, exc_info=True)
            raise exc

        # Stage 9: Record immutable operational audit event
        await self.audit_tool.execute(
            action="investigation_completed",
            resource_type="investigation_case",
            resource_id=str(case_id),
            user_id=current_user.id if current_user else None,
            case_id=case_id,
            details={
                "case_number": case_number,
                "payment_reference": payment_lookup.payment_reference,
                "issue_category": triage_result.category,
                "rule_matched": triage_result.rule_id_matched,
                "confidence": triage_result.confidence_score,
                "retrieval_mode": retrieval_result.retrieval_mode,
                "generation_mode": explanation_result.generation_mode,
                "execution_time_ms": execution_time_ms,
                "human_review_required": db_result.human_review_required,
                "rejected_citations": explanation_result.rejected_citations_count,
            },
        )

        # Stage 10: Reload with relationships and return validated response
        stmt = (
            select(InvestigationCase)
            .where(InvestigationCase.id == case_id)
            .options(
                selectinload(InvestigationCase.payment),
                selectinload(InvestigationCase.result),
            )
        )
        loaded = await self.session.execute(stmt)
        case_obj = loaded.scalar_one()

        return InvestigationCaseResponse.model_validate(case_obj)
