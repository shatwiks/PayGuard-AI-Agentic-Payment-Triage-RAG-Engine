"""Tests verifying SQLAlchemy models, entity relationships, and constraints."""

from datetime import datetime, timezone
from decimal import Decimal
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User
from backend.app.models.payment import Payment, PaymentEvent
from backend.app.models.investigation import InvestigationCase, InvestigationResult
from backend.app.models.knowledge import KnowledgeDocument, DocumentChunk
from backend.app.models.audit import AuditEvent


@pytest.mark.asyncio
async def test_user_persistence_and_relationships(db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        email="analyst@payguard.ai",
        hashed_password="hashed_pwd_placeholder",
        full_name="Operations Analyst",
        role="support_agent",
    )
    db_session.add(user)
    await db_session.commit()

    stmt = select(User).where(User.email == "analyst@payguard.ai")
    res = await db_session.execute(stmt)
    saved_user = res.scalar_one()

    assert saved_user.id == user.id
    assert saved_user.role == "support_agent"
    assert saved_user.is_active is True


@pytest.mark.asyncio
async def test_payment_and_payment_events(db_session: AsyncSession):
    payment_id = uuid.uuid4()
    payment = Payment(
        id=payment_id,
        payment_reference="tx_20261020_0001",
        customer_id="cust_8821",
        merchant_id="merch_1001",
        amount=Decimal("49.99"),
        currency="USD",
        payment_method="credit_card",
        status="failed",
        gateway_name="stripe",
        failure_code="card_expired",
        failure_message="The card expiration date is invalid.",
    )
    event = PaymentEvent(
        id=uuid.uuid4(),
        payment_id=payment_id,
        event_type="gateway_webhook",
        from_status="pending",
        to_status="failed",
        raw_payload={"error": {"code": "card_expired"}},
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(payment)
    db_session.add(event)
    await db_session.commit()

    stmt = select(Payment).where(Payment.id == payment_id)
    res = await db_session.execute(stmt)
    saved = res.scalar_one()

    assert saved.payment_reference == "tx_20261020_0001"
    assert saved.amount == Decimal("49.99")
    assert saved.status == "failed"


@pytest.mark.asyncio
async def test_investigation_case_and_result(db_session: AsyncSession):
    case_id = uuid.uuid4()
    case = InvestigationCase(
        id=case_id,
        case_number="CASE-20261020-001",
        customer_query="I was double charged $49.99 yesterday.",
        sanitized_query="I was double charged $49.99 yesterday.",
        status="triaged",
        priority="high",
    )
    result = InvestigationResult(
        id=uuid.uuid4(),
        case_id=case_id,
        issue_category="duplicate_charge",
        confidence_score=0.94,
        investigation_summary="Identified duplicate authorization attempt.",
        recommended_action="VOID_PENDING_AUTHORIZATION",
        recommended_action_details="Release pending authorization hold.",
        policy_citations=[{"title": "Billing SLA", "section": "Sec 4"}],
        execution_time_ms=145,
    )
    db_session.add(case)
    db_session.add(result)
    await db_session.commit()

    stmt = select(InvestigationCase).where(InvestigationCase.id == case_id)
    res = await db_session.execute(stmt)
    saved_case = res.scalar_one()

    assert saved_case.status == "triaged"
    assert saved_case.priority == "high"


@pytest.mark.asyncio
async def test_knowledge_document_and_chunks(db_session: AsyncSession):
    doc_id = uuid.uuid4()
    doc = KnowledgeDocument(
        id=doc_id,
        title="NACHA ACH Dispute Rules",
        doc_type="scheme_rules",
        version="2026.1",
    )
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=0,
        section_header="Return Reason Code R01",
        content="R01 - Insufficient Funds: Available balance is not sufficient to cover the debit entry.",
        token_count=18,
        embedding=[0.01] * 1536,
    )
    db_session.add(doc)
    db_session.add(chunk)
    await db_session.commit()

    stmt = select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id)
    res = await db_session.execute(stmt)
    saved_doc = res.scalar_one()

    assert saved_doc.title == "NACHA ACH Dispute Rules"
    assert saved_doc.is_active is True
