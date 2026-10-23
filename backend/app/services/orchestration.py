"""Investigation Orchestration Service coordinating the triage pipeline."""

from datetime import datetime, timezone
import time
from typing import Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from backend.app.core.security import mask_pii
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


class OrchestrationService(IOrchestrationService):
    """Coordinates the entire payment investigation lifecycle:
    1. Validate & sanitize PII
    2. Lookup payment record (if reference provided)
    3. Run deterministic triage engine
    4. Retrieve relevant policy chunks via pgvector RAG
    5. Generate grounded explanation via LLM reasoning
    6. Persist investigation case and result
    7. Record immutable audit events
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

    async def run_investigation(
        self,
        request: InvestigationCreateRequest,
        current_user: Optional[UserResponse] = None,
    ) -> InvestigationCaseResponse:
        start_time = time.perf_counter()

        # Step 1: Sanitize and Mask PII
        sanitized_query = mask_pii(request.customer_query)

        # Step 2: Fetch payment details if reference or ID provided
        payment = None
        if request.payment_id:
            payment = await self.payment_service.get_payment_details(request.payment_id)
        elif request.payment_reference:
            payment = await self.payment_service.get_payment_by_reference(request.payment_reference)

        # Step 3: Run deterministic triage classification
        triage_result = self.triage_engine.classify_payment_issue(
            payment=payment,
            user_query=sanitized_query,
        )

        # Step 4: Retrieve policy citations via RAG
        citations = await self.rag_service.retrieve_troubleshooting_docs(
            query=sanitized_query,
            issue_category=triage_result.category,
            top_k=3,
        )

        # Step 5: Generate grounded investigation summary via LLM
        llm_output = await self.llm_service.generate_investigation_summary(
            user_query=sanitized_query,
            payment=payment,
            citations=citations,
            triage_result=triage_result,
        )

        execution_time_ms = int((time.perf_counter() - start_time) * 1000)

        # Step 6: Create and persist InvestigationCase & InvestigationResult
        case_id = uuid.uuid4()
        case_number = f"CASE-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(case_id)[:8].upper()}"

        db_case = InvestigationCase(
            id=case_id,
            case_number=case_number,
            payment_id=payment.id if payment else None,
            created_by_user_id=current_user.id if current_user else None,
            customer_query=request.customer_query,
            sanitized_query=sanitized_query,
            status="triaged",
            priority=request.priority or "medium",
        )

        citations_data = [c.model_dump() for c in citations]

        db_result = InvestigationResult(
            id=uuid.uuid4(),
            case_id=case_id,
            issue_category=triage_result.category,
            confidence_score=triage_result.confidence_score,
            investigation_summary=llm_output.investigation_summary,
            recommended_action=llm_output.recommended_action,
            recommended_action_details=llm_output.recommended_action_details,
            policy_citations=citations_data,
            missing_or_conflicting_info=llm_output.missing_or_conflicting_info,
            human_review_required=llm_output.human_review_required or triage_result.is_ambiguous,
            human_review_reason=llm_output.human_review_reason,
            execution_time_ms=execution_time_ms,
            llm_model_name=llm_output.model_name,
        )

        self.session.add(db_case)
        self.session.add(db_result)
        await self.session.commit()

        # Step 7: Record Audit Event
        await self.audit_service.log_audit_event(
            action="investigation_completed",
            resource_type="investigation_case",
            resource_id=str(case_id),
            user_id=current_user.id if current_user else None,
            case_id=case_id,
            details={
                "issue_category": triage_result.category,
                "confidence": triage_result.confidence_score,
                "execution_time_ms": execution_time_ms,
                "human_review_required": db_result.human_review_required,
            },
        )

        # Reload with relationships
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
