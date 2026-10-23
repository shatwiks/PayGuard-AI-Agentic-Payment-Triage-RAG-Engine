"""Unit and idempotency tests for synthetic payment and knowledge base seed datasets."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.knowledge import DocumentChunk, KnowledgeDocument
from backend.app.models.payment import Payment, PaymentEvent
from backend.app.models.user import User
from backend.app.scripts.seed_data import (
    seed_knowledge_documents,
    seed_payments_and_events,
    seed_users,
)


@pytest.mark.asyncio
async def test_seed_users_idempotency(db_session: AsyncSession):
    """Verify seed_users creates 3 demo accounts and is completely idempotent on repeated execution."""
    # First execution
    users_first = await seed_users(db_session)
    assert len(users_first) == 3

    # Count records
    count_stmt = select(func.count(User.id))
    count_1 = (await db_session.execute(count_stmt)).scalar_one()
    assert count_1 == 3

    # Second execution (idempotency check)
    users_second = await seed_users(db_session)
    assert len(users_second) == 3

    count_2 = (await db_session.execute(count_stmt)).scalar_one()
    assert count_2 == 3


@pytest.mark.asyncio
async def test_seed_payments_and_events_distribution(db_session: AsyncSession):
    """Verify seed_payments_and_events generates varied scenarios and maintains idempotency."""
    # Seed payments
    payments_first = await seed_payments_and_events(db_session)
    assert len(payments_first) == 40

    # Verify event counts
    payment_count = (await db_session.execute(select(func.count(Payment.id)))).scalar_one()
    event_count = (await db_session.execute(select(func.count(PaymentEvent.id)))).scalar_one()

    assert payment_count == 40
    assert event_count >= 70

    # Verify scenario coverage across statuses
    statuses = set(p.status for p in payments_first)
    expected_statuses = {"captured", "pending", "failed", "authorized", "refunded", "disputed"}
    assert expected_statuses.issubset(statuses)

    # Re-running seed must be idempotent (no duplicate rows created)
    payments_second = await seed_payments_and_events(db_session)
    assert len(payments_second) == 40

    payment_count_after = (await db_session.execute(select(func.count(Payment.id)))).scalar_one()
    event_count_after = (await db_session.execute(select(func.count(PaymentEvent.id)))).scalar_one()

    assert payment_count_after == 40
    assert event_count_after == event_count


@pytest.mark.asyncio
async def test_seed_knowledge_documents_provenance(db_session: AsyncSession):
    """Verify policy documents have valid metadata, source provenance, and chunk splits."""
    docs_first = await seed_knowledge_documents(db_session)
    assert len(docs_first) == 4

    doc_count = (await db_session.execute(select(func.count(KnowledgeDocument.id)))).scalar_one()
    chunk_count = (await db_session.execute(select(func.count(DocumentChunk.id)))).scalar_one()

    assert doc_count == 4
    assert chunk_count == 8

    # Verify provenance on documents
    for doc in docs_first:
        assert doc.source_url is not None
        assert doc.doc_type in ("scheme_rules", "refund_policy", "dispute_guide", "sla_spec")
        assert doc.version is not None
        assert len(doc.title) > 5

    # Re-running seed must be idempotent
    docs_second = await seed_knowledge_documents(db_session)
    assert len(docs_second) == 4

    doc_count_after = (await db_session.execute(select(func.count(KnowledgeDocument.id)))).scalar_one()
    chunk_count_after = (await db_session.execute(select(func.count(DocumentChunk.id)))).scalar_one()

    assert doc_count_after == 4
    assert chunk_count_after == chunk_count
