"""Investigations API router for executing automated payment triage workflows."""

import math
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.database import get_db
from backend.app.core.errors import EntityNotFoundException, ForbiddenException, UnauthorizedException
from backend.app.core.rate_limit import rate_limit
from backend.app.models.investigation import InvestigationCase, InvestigationResult
from backend.app.schemas.common import PaginatedResponse
from backend.app.schemas.investigation import (
    InvestigationCaseResponse,
    InvestigationCreateRequest,
    InvestigationMetricsResponse,
)
from backend.app.services.audit import AuditService
from backend.app.services.llm import LLMReasoningService
from backend.app.services.orchestration import OrchestrationService
from backend.app.services.payment import PaymentService
from backend.app.services.rag import RagService
from backend.app.services.triage import TriageRulesEngine

from backend.app.core.security import get_optional_current_user
from backend.app.models.user import User
from backend.app.schemas.auth import UserResponse
from backend.app.core.config import settings

router = APIRouter(prefix="/investigations", tags=["Investigations"])


@router.post(
    "",
    response_model=InvestigationCaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start Automated Payment Investigation",
    description="Submits customer issue and payment reference for automated deterministic triage, pgvector RAG retrieval, and grounded explanation.",
)
async def create_investigation(
    request: InvestigationCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
    _rate_guard: None = Depends(rate_limit("create_investigation", max_requests=settings.RATE_LIMIT_INVESTIGATIONS_PER_MINUTE)),
) -> InvestigationCaseResponse:
    # Instantiate modular service layers
    payment_service = PaymentService(db)
    triage_engine = TriageRulesEngine()
    rag_service = RagService(db)
    llm_service = LLMReasoningService()
    audit_service = AuditService(db)

    orchestrator = OrchestrationService(
        session=db,
        payment_service=payment_service,
        triage_engine=triage_engine,
        rag_service=rag_service,
        llm_service=llm_service,
        audit_service=audit_service,
    )

    user_resp = UserResponse.model_validate(current_user) if current_user else None
    return await orchestrator.run_investigation(request=request, current_user=user_resp)


@router.get(
    "/metrics",
    response_model=InvestigationMetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Real Investigation Metrics",
    description="Calculate real backend metrics grouped by case status and issue category scoped to user role.",
)
async def get_investigation_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> InvestigationMetricsResponse:
    conditions = []
    if current_user and current_user.role == "support_agent":
        conditions.append(
            (InvestigationCase.created_by_user_id == current_user.id)
            | (InvestigationCase.created_by_user_id == None)  # noqa: E711
        )
    elif not current_user:
        conditions.append(InvestigationCase.created_by_user_id == None)  # noqa: E711

    # Status counts
    status_stmt = select(InvestigationCase.status, func.count(InvestigationCase.id)).group_by(InvestigationCase.status)
    if conditions:
        status_stmt = status_stmt.where(*conditions)
    status_res = await db.execute(status_stmt)
    status_counts = dict(status_res.all())

    total = sum(status_counts.values())

    # Category counts
    cat_stmt = (
        select(InvestigationResult.issue_category, func.count(InvestigationResult.id))
        .join(InvestigationCase, InvestigationCase.id == InvestigationResult.case_id)
        .group_by(InvestigationResult.issue_category)
    )
    if conditions:
        cat_stmt = cat_stmt.where(*conditions)
    cat_res = await db.execute(cat_stmt)
    category_counts = dict(cat_res.all())

    return InvestigationMetricsResponse(
        total_cases=total,
        open_cases=status_counts.get("open", 0),
        in_progress_cases=status_counts.get("in_progress", 0),
        triaged_cases=status_counts.get("triaged", 0),
        escalated_cases=status_counts.get("escalated", 0),
        closed_cases=status_counts.get("closed", 0),
        by_category=category_counts,
    )


@router.get(
    "/{investigation_id}",
    response_model=InvestigationCaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Investigation Case by ID",
    description="Retrieve full investigation record, including triage result, evidence citations, and recommended action with role-based access control.",
)
async def get_investigation(
    investigation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> InvestigationCaseResponse:
    stmt = (
        select(InvestigationCase)
        .where(InvestigationCase.id == investigation_id)
        .options(
            selectinload(InvestigationCase.payment),
            selectinload(InvestigationCase.result),
        )
    )
    result = await db.execute(stmt)
    case_obj = result.scalar_one_or_none()
    if not case_obj:
        raise EntityNotFoundException("InvestigationCase", str(investigation_id))

    # Enforce ownership / authorization checks
    if case_obj.created_by_user_id is not None:
        if not current_user:
            raise UnauthorizedException("Authentication required to access this private investigation case.")
        if current_user.role not in ("admin", "compliance_analyst") and current_user.id != case_obj.created_by_user_id:
            raise ForbiddenException("You do not have permission to access another operator's private investigation case.")

    return InvestigationCaseResponse.model_validate(case_obj)


@router.get(
    "",
    response_model=PaginatedResponse[InvestigationCaseResponse],
    status_code=status.HTTP_200_OK,
    summary="List and Filter Investigation Cases",
    description="Retrieve paginated history of investigation cases filtered by status, priority, and user authorization scope.",
)
async def list_investigations(
    case_status: Optional[str] = Query(None, alias="status", description="Filter by case status"),
    priority: Optional[str] = Query(None, description="Filter by case priority"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> PaginatedResponse[InvestigationCaseResponse]:
    conditions = []
    if case_status:
        conditions.append(InvestigationCase.status == case_status)
    if priority:
        conditions.append(InvestigationCase.priority == priority)

    # Scoped filtering based on user permissions
    if current_user and current_user.role == "support_agent":
        conditions.append(
            (InvestigationCase.created_by_user_id == current_user.id)
            | (InvestigationCase.created_by_user_id == None)  # noqa: E711
        )
    elif not current_user:
        # Unauthenticated users only see public unassigned test cases
        conditions.append(InvestigationCase.created_by_user_id == None)  # noqa: E711

    count_stmt = select(func.count(InvestigationCase.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    count_res = await db.execute(count_stmt)
    total = count_res.scalar_one()

    offset = (page - 1) * page_size
    stmt = (
        select(InvestigationCase)
        .order_by(InvestigationCase.created_at.desc())
        .options(
            selectinload(InvestigationCase.payment),
            selectinload(InvestigationCase.result),
        )
        .offset(offset)
        .limit(page_size)
    )
    if conditions:
        stmt = stmt.where(*conditions)

    res = await db.execute(stmt)
    cases = res.scalars().all()

    items = [InvestigationCaseResponse.model_validate(c) for c in cases]
    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )

