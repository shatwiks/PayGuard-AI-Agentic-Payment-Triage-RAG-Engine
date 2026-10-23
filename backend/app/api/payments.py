"""Payments API router providing read-only transaction queries and event telemetry."""

import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.errors import EntityNotFoundException
from backend.app.schemas.common import PaginatedResponse, PaginationParams
from backend.app.schemas.payment import (
    PaymentDetailResponse,
    PaymentFilterParams,
    PaymentSummaryResponse,
)
from backend.app.services.payment import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get(
    "",
    response_model=PaginatedResponse[PaymentSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="List and Search Payment Transactions",
    description="Retrieve paginated payment records filtered by reference, customer ID, status, or gateway.",
)
async def list_payments(
    payment_reference: str = Query(None, description="Exact or partial payment reference code"),
    customer_id: str = Query(None, description="Customer identifier"),
    merchant_id: str = Query(None, description="Merchant account ID"),
    status_filter: str = Query(None, alias="status", description="Payment lifecycle status"),
    payment_method: str = Query(None, description="Payment rail"),
    gateway_name: str = Query(None, description="Processor name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[PaymentSummaryResponse]:
    filters = PaymentFilterParams(
        payment_reference=payment_reference,
        customer_id=customer_id,
        merchant_id=merchant_id,
        status=status_filter,
        payment_method=payment_method,
        gateway_name=gateway_name,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    service = PaymentService(db)
    return await service.search_payment_records(filters, pagination)


@router.get(
    "/{payment_id}",
    response_model=PaymentDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Payment Details by ID",
    description="Retrieve detailed transaction information including gateway metadata and chronological event timeline.",
)
async def get_payment(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PaymentDetailResponse:
    service = PaymentService(db)
    payment = await service.get_payment_details(payment_id)
    if not payment:
        raise EntityNotFoundException("Payment", str(payment_id))
    return payment
