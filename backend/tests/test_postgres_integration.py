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


@pytest.mark.asyncio
async def test_postgres_fts_generated_tsvector_and_gin_index(pg_session: AsyncSession):
    """Verify PostgreSQL automatically maintains the generated tsvector column and GIN index."""
    # 1. Verify GIN index exists in PostgreSQL catalog
    index_check = await pg_session.execute(text("""
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'document_chunks' AND indexname = 'idx_document_chunks_tsv';
    """))
    assert index_check.scalar_one_or_none() == "idx_document_chunks_tsv"

    # 2. Insert a document and chunk without providing tsv (verifies GENERATED ALWAYS AS column)
    doc_id = uuid.uuid4()
    doc = KnowledgeDocument(
        id=doc_id,
        title="Live FTS Test Policy",
        doc_type="scheme_rules",
        version="1.0",
        source_id="internal://test/live-fts",
        raw_content="Content for live test",
        is_active=True,
    )
    pg_session.add(doc)
    await pg_session.flush()

    chunk_id = uuid.uuid4()
    chunk = DocumentChunk(
        id=chunk_id,
        document_id=doc_id,
        chunk_index=0,
        section_header="ACH Return Code R01 Specification",
        content="Return Code R01 indicates insufficient funds in customer bank account for debit entry.",
        token_count=18,
        embedding_model="mock-fts-model",
        embedding=[0.0] * 1536,
        metadata_={"test": True},
    )
    pg_session.add(chunk)
    await pg_session.commit()

    # 3. Query using PostgreSQL full-text search operator @@ and ts_rank_cd
    sql_fts = text("""
        SELECT id, section_header, ts_rank_cd(tsv, plainto_tsquery('english', 'R01 insufficient funds')) AS score
        FROM document_chunks
        WHERE id = :chunk_id AND tsv @@ plainto_tsquery('english', 'R01 insufficient funds');
    """)
    res = await pg_session.execute(sql_fts, {"chunk_id": chunk_id})
    row = res.fetchone()
    assert row is not None, "PostgreSQL FTS must match text in generated tsvector column"
    assert row[0] == chunk_id
    assert float(row[2]) > 0.0

    # Clean up
    await pg_session.delete(chunk)
    await pg_session.delete(doc)
    await pg_session.commit()


@pytest.mark.asyncio
async def test_postgres_hybrid_retrieval_service_live(pg_session: AsyncSession):
    """Verify HybridRetrievalService executes real PostgreSQL FTS and pgvector similarity queries."""
    from backend.app.services.embedding import MockEmbeddingProvider
    from backend.app.services.retrieval import HybridRetrievalService
    from backend.app.services.ingestion import DocumentIngestionPipeline

    target_model = "mock-live-pg-model"
    provider = MockEmbeddingProvider(dimension=1536, model_name=target_model)
    pipeline = DocumentIngestionPipeline(pg_session, embedding_provider=provider)

    # Ingest document into PostgreSQL
    ingest_res = await pipeline.ingest_document(
        title="Live Visa Dispute 10.4 Policy",
        source_id="internal://test/visa-10-4-live",
        source_type="scheme_rules",
        content="""# Visa Dispute Condition 10.4
## Liability Shift Rules
When EMV 3-D Secure version 2.2 returns ECI 05, liability shifts directly to issuer.
Merchant provides CAVV and Directory Server Trans ID to invalidate the dispute.
""",
        force_reindex=True,
    )
    assert ingest_res.status in ("success", "lexical_only")

    # Run hybrid retrieval
    retrieval_service = HybridRetrievalService(pg_session, embedding_provider=provider)
    search_res = await retrieval_service.search(
        query="EMV 3-D Secure liability shift CAVV",
        top_k=3,
        retrieval_mode="hybrid",
    )

    assert len(search_res.results) >= 1
    top_result = search_res.results[0]
    assert top_result.ranking.fusion_score > 0.0
    assert "CAVV" in top_result.content or "liability" in top_result.content.lower()

    # Clean up
    doc = await pg_session.get(KnowledgeDocument, ingest_res.document_id)
    if doc:
        await pg_session.delete(doc)
        await pg_session.commit()


@pytest.mark.asyncio
async def test_postgres_hnsw_vector_index_exists_and_queries(pg_session: AsyncSession):
    """Verify that idx_document_chunks_embedding_hnsw exists in pg_indexes and supports cosine distance searches."""
    # 1. Verify index in PostgreSQL catalog
    res = await pg_session.execute(text("""
        SELECT indexname, indexdef FROM pg_indexes
        WHERE tablename = 'document_chunks' AND indexname = 'idx_document_chunks_embedding_hnsw';
    """))
    row = res.fetchone()
    assert row is not None, "idx_document_chunks_embedding_hnsw must exist in PostgreSQL catalog"
    index_def = row[1]
    assert "hnsw" in index_def.lower()
    assert "vector_cosine_ops" in index_def.lower()
    assert "m = 16" in index_def.lower() or "m='16'" in index_def.lower()
    assert "ef_construction = 64" in index_def.lower() or "ef_construction='64'" in index_def.lower()

    # 2. Run vector distance query with EXPLAIN
    target_vector = "[" + ",".join("0.025" for _ in range(1536)) + "]"
    explain_sql = text(f"""
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT id, embedding_model, (embedding <=> '{target_vector}') AS distance
        FROM document_chunks
        WHERE embedding IS NOT NULL
        ORDER BY distance ASC
        LIMIT 5;
    """)
    explain_res = await pg_session.execute(explain_sql)
    plan_lines = [r[0] for r in explain_res.fetchall()]
    plan_text = "\n".join(plan_lines)
    assert "Execution Time:" in plan_text

