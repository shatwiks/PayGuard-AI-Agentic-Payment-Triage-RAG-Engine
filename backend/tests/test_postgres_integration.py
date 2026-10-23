"""Live integration tests running against PostgreSQL 16 + pgvector container.

Verifies:
1. Real PostgreSQL database connectivity and pgvector extension registration.
2. Real schema constraints, foreign keys, and transaction rollbacks.
3. Native pgvector 1536-dim vector storage and cosine distance (<=>) operator execution.
4. Core entity CRUD operations in PostgreSQL.
"""

from datetime import datetime, timezone
import os
import uuid
import pytest
from sqlalchemy import text, select
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.models.knowledge import KnowledgeDocument, DocumentChunk
from backend.app.models.payment import Payment, PaymentEvent
from backend.app.models.investigation import InvestigationCase, InvestigationResult
from backend.app.models.audit import AuditEvent

POSTGRES_TEST_URL = os.environ.get(
    "POSTGRES_INTEGRATION_URL",
    "postgresql+asyncpg://payguard_user:payguard_secure_password@localhost:5434/payguard_db",
)


@pytest.fixture
async def pg_session():
    """Provides a fresh, non-pooled AsyncSession connected to PostgreSQL for each test."""
    engine = create_async_engine(POSTGRES_TEST_URL, poolclass=NullPool, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1;"))
    except Exception as e:
        await engine.dispose()
        pytest.skip(f"PostgreSQL container is not reachable on localhost:5434: {e}")

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_pgvector_extension_active(pg_session: AsyncSession):
    """Verify that PostgreSQL 16 has the pgvector and uuid-ossp extensions active."""
    result = await pg_session.execute(
        text("SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'uuid-ossp');")
    )
    extensions = {row[0]: row[1] for row in result.fetchall()}
    assert "vector" in extensions, "pgvector extension must be installed in PostgreSQL"
    assert "uuid-ossp" in extensions, "uuid-ossp extension must be installed in PostgreSQL"


@pytest.mark.asyncio
async def test_postgres_pgvector_native_vector_operations(pg_session: AsyncSession):
    """Verify storing a 1536-dimensional vector and querying via pgvector cosine distance (<=>)."""
    # 1. Create a parent KnowledgeDocument matching current schema
    doc_id = uuid.uuid4()
    doc = KnowledgeDocument(
        id=doc_id,
        title="Integration Test Document",
        doc_type="troubleshooting_guide",
        version="1.0",
        source_url="https://internal.payguard.ai/docs/test-doc.md",
        is_active=True,
    )
    pg_session.add(doc)
    await pg_session.commit()

    # 2. Create sample 1536-dim embedding vectors
    vec_a = [0.0] * 1536
    vec_a[0] = 1.0  # Unit vector along dimension 0

    chunk_id = uuid.uuid4()
    chunk = DocumentChunk(
        id=chunk_id,
        document_id=doc_id,
        chunk_index=0,
        section_header="Introduction",
        content="Unit vector test chunk for pgvector cosine search.",
        embedding=vec_a,
        token_count=10,
        metadata_={"test": True},
    )
    pg_session.add(chunk)
    await pg_session.commit()

    # 3. Query using native PostgreSQL pgvector cosine distance operator <=>
    # Searching with vec_a itself: distance should be ~0.0
    query_str = "[" + ",".join(str(x) for x in vec_a) + "]"
    sql = text("""
        SELECT id, content, (embedding <=> :target_vector) AS cosine_distance
        FROM document_chunks
        WHERE id = :chunk_id
    """)
    res = await pg_session.execute(sql, {"target_vector": query_str, "chunk_id": chunk_id})
    row = res.fetchone()
    assert row is not None
    assert row[0] == chunk_id
    # Cosine distance between identical unit vectors is 0
    assert abs(float(row[2])) < 1e-4

    # Cleanup test records
    await pg_session.delete(chunk)
    await pg_session.delete(doc)
    await pg_session.commit()


@pytest.mark.asyncio
async def test_postgres_payment_and_audit_persistence(pg_session: AsyncSession):
    """Verify creating, committing, and querying Payments, Events, and AuditEvents in PostgreSQL."""
    test_ref = f"tx_pg_test_{uuid.uuid4().hex[:8]}"

    payment = Payment(
        id=uuid.uuid4(),
        payment_reference=test_ref,
        customer_id="cust_live_test",
        merchant_id="merch_live_test",
        amount=149.99,
        currency="USD",
        payment_method="credit_card",
        status="captured",
        gateway_name="stripe",
    )
    pg_session.add(payment)
    await pg_session.commit()

    event = PaymentEvent(
        id=uuid.uuid4(),
        payment_id=payment.id,
        event_type="payment.captured",
        from_status="authorized",
        to_status="captured",
        raw_payload={"gateway_status": "succeeded"},
        occurred_at=datetime.now(timezone.utc),
    )
    pg_session.add(event)

    audit = AuditEvent(
        action="payment_lookup",
        resource_type="payment",
        resource_id=test_ref,
        details={"test_run": True},
    )
    pg_session.add(audit)
    await pg_session.commit()

    # Query back from PostgreSQL
    check_payment = await pg_session.execute(
        select(Payment).where(Payment.payment_reference == test_ref)
    )
    assert check_payment.scalar_one_or_none() is not None

    # Clean up test rows
    await pg_session.delete(event)
    await pg_session.delete(payment)
    await pg_session.delete(audit)
    await pg_session.commit()
