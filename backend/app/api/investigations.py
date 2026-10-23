"""Investigations API router for executing automated payment triage workflows."""

import math
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.database import get_db
from backend.app.core.errors import EntityNotFoundException
from backend.app.models.investigation import InvestigationCase
from backend.app.schemas.common import PaginatedResponse
from backend.app.schemas.investigation import (
    InvestigationCaseResponse,
    InvestigationCreateRequest,
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
    "/{investigation_id}",
    response_model=InvestigationCaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Investigation Case by ID",
    description="Retrieve full investigation record, including triage result, evidence citations, and recommended action.",
)
async def get_investigation(
    investigation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
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

    return InvestigationCaseResponse.model_validate(case_obj)


@router.get(
    "",
    response_model=PaginatedResponse[InvestigationCaseResponse],
    status_code=status.HTTP_200_OK,
    summary="List and Filter Investigation Cases",
    description="Retrieve paginated history of investigation cases filtered by status or priority.",
)
async def list_investigations(
    case_status: Optional[str] = Query(None, alias="status", description="Filter by case status"),
    priority: Optional[str] = Query(None, description="Filter by case priority"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[InvestigationCaseResponse]:
    conditions = []
    if case_status:
        conditions.append(InvestigationCase.status == case_status)
    if priority:
        conditions.append(InvestigationCase.priority == priority)

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
