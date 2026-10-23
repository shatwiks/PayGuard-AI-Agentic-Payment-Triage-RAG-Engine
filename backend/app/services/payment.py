"""Payment service providing safe, read-only data access to transactions and event telemetry."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.payment import Payment, PaymentEvent
from backend.app.schemas.common import PaginatedResponse, PaginationParams
from backend.app.schemas.payment import (
    PaymentDetailResponse,
    PaymentEventResponse,
    PaymentFilterParams,
    PaymentSummaryResponse,
)
from backend.app.services.interfaces import IPaymentService


class PaymentService(IPaymentService):
    """Encapsulates parameterized queries and read-only access to payment tables."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_payment_details(self, payment_id: uuid.UUID) -> Optional[PaymentDetailResponse]:
        query = (
            select(Payment)
            .where(Payment.id == payment_id)
            .options(selectinload(Payment.events))
        )
        result = await self.session.execute(query)
        payment = result.scalar_one_or_none()
        if not payment:
            return None
        return PaymentDetailResponse.model_validate(payment)

    async def get_payment_by_reference(self, reference: str) -> Optional[PaymentDetailResponse]:
        query = (
            select(Payment)
            .where(Payment.payment_reference == reference)
            .options(selectinload(Payment.events))
        )
        result = await self.session.execute(query)
        payment = result.scalar_one_or_none()
        if not payment:
            return None
        return PaymentDetailResponse.model_validate(payment)

    async def get_payment_history(self, payment_id: uuid.UUID) -> List[PaymentEventResponse]:
        query = (
            select(PaymentEvent)
            .where(PaymentEvent.payment_id == payment_id)
            .order_by(PaymentEvent.occurred_at.asc())
        )
        result = await self.session.execute(query)
        events = result.scalars().all()
        return [PaymentEventResponse.model_validate(e) for e in events]

    async def search_payment_records(
        self,
        filters: PaymentFilterParams,
        pagination: PaginationParams,
    ) -> PaginatedResponse[PaymentSummaryResponse]:
        conditions = []
        if filters.payment_reference:
            conditions.append(Payment.payment_reference.ilike(f"%{filters.payment_reference}%"))
        if filters.customer_id:
            conditions.append(Payment.customer_id == filters.customer_id)
        if filters.merchant_id:
            conditions.append(Payment.merchant_id == filters.merchant_id)
        if filters.status:
            conditions.append(Payment.status == filters.status)
        if filters.payment_method:
            conditions.append(Payment.payment_method == filters.payment_method)
        if filters.gateway_name:
            conditions.append(Payment.gateway_name == filters.gateway_name)

        # Count total
        count_query = select(func.count(Payment.id))
        if conditions:
            count_query = count_query.where(*conditions)
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # Query paginated slice
        offset = (pagination.page - 1) * pagination.page_size
        items_query = (
            select(Payment)
            .order_by(Payment.created_at.desc())
            .offset(offset)
            .limit(pagination.page_size)
        )
        if conditions:
            items_query = items_query.where(*conditions)

        items_result = await self.session.execute(items_query)
        payments = items_result.scalars().all()

        return PaginatedResponse.create(
            items=[PaymentSummaryResponse.model_validate(p) for p in payments],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def create_payment(
        self,
        payment_reference: str,
        customer_id: str,
        merchant_id: str,
        amount: Decimal,
        currency: str,
        payment_method: str,
        status: str,
        gateway_name: str,
        gateway_transaction_id: Optional[str] = None,
        failure_code: Optional[str] = None,
        failure_message: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
        authorized_at: Optional[datetime] = None,
        captured_at: Optional[datetime] = None,
    ) -> Payment:
        payment = Payment(
            id=uuid.uuid4(),
            payment_reference=payment_reference,
            customer_id=customer_id,
            merchant_id=merchant_id,
            amount=amount,
            currency=currency.upper(),
            payment_method=payment_method,
            status=status,
            gateway_name=gateway_name,
            gateway_transaction_id=gateway_transaction_id,
            failure_code=failure_code,
            failure_message=failure_message,
            metadata_=metadata_ or {},
            authorized_at=authorized_at,
            captured_at=captured_at,
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def create_payment_event(
        self,
        payment_id: uuid.UUID,
        event_type: str,
        to_status: str,
        from_status: Optional[str] = None,
        raw_payload: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[datetime] = None,
    ) -> PaymentEvent:
        event = PaymentEvent(
            id=uuid.uuid4(),
            payment_id=payment_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            raw_payload=raw_payload or {},
            occurred_at=occurred_at or datetime.now(timezone.utc),
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event
