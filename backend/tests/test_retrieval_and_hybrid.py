"""Unit and integration tests for RAG ingestion pipeline, lexical search, semantic search, hybrid RRF, and retrieval API."""

from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import create_access_token
from backend.app.models.knowledge import DocumentChunk, KnowledgeDocument
from backend.app.models.user import User
from backend.app.schemas.knowledge import KnowledgeSearchRequest, KnowledgeSearchResponse
from backend.app.services.chunker import DocumentChunker
from backend.app.services.embedding import MockEmbeddingProvider, OpenAIEmbeddingProvider
from backend.app.services.ingestion import DocumentIngestionPipeline
from backend.app.services.retrieval import HybridRetrievalService


@pytest.fixture
def mock_embedding_provider():
    return MockEmbeddingProvider(dimension=1536, model_name="mock-test-1536")


@pytest.fixture
def offline_embedding_provider():
    return MockEmbeddingProvider(dimension=1536, model_name="mock-test-1536", available=False)


@pytest.mark.asyncio
async def test_document_ingestion_and_chunk_provenance(db_session: AsyncSession, mock_embedding_provider):
    """Verify document ingestion splits document into chunks with preserved source provenance and embeddings."""
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=mock_embedding_provider)

    markdown_content = """# Payment Timeout Policy
## Automatic Reversals
If an authorization is pending beyond 48 hours without a capture event, the hold is voided.

## Gateway Error Code R01
Error code R01 denotes insufficient funds reported by the issuing bank.
"""

    doc, chunks = await pipeline.ingest_document(
        title="Payment Timeout and Return Codes",
        source_id="internal://test-policies/timeouts-and-returns",
        source_type="chargeback_rule",
        content=markdown_content,
        metadata={"version": "1.0", "author": "risk-team"},
    )

    assert doc.id is not None
    assert doc.source_id == "internal://test-policies/timeouts-and-returns"
    assert doc.source_type == "chargeback_rule"
    assert doc.content_hash is not None
    assert doc.raw_content == markdown_content

    assert len(chunks) == 2
    # Verify provenance on chunks
    assert chunks[0].document_id == doc.id
    assert chunks[0].source_id == "internal://test-policies/timeouts-and-returns"
    assert chunks[0].chunk_index == 0
    assert chunks[0].section_header == "Automatic Reversals"
    assert chunks[0].embedding_model == "mock-test-1536"
    assert len(chunks[0].embedding) == 1536

    assert chunks[1].chunk_index == 1
    assert "R01" in chunks[1].content
    assert chunks[1].embedding_model == "mock-test-1536"


@pytest.mark.asyncio
async def test_document_ingestion_idempotency(db_session: AsyncSession, mock_embedding_provider):
    """Verify ingesting identical content does not duplicate documents or chunks."""
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=mock_embedding_provider)
    content = "# Static Policy\nThis content does not change."

    doc1, chunks1 = await pipeline.ingest_document(
        title="Static Policy",
        source_id="internal://test-policies/static-1",
        source_type="gateway_spec",
        content=content,
    )

    # Ingest again
    doc2, chunks2 = await pipeline.ingest_document(
        title="Static Policy",
        source_id="internal://test-policies/static-1",
        source_type="gateway_spec",
        content=content,
    )

    assert doc1.id == doc2.id
    assert len(chunks1) == len(chunks2)

    # Verify database total chunk count
    result = await db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc1.id)
    )
    all_chunks = result.scalars().all()
    assert len(all_chunks) == len(chunks1)


@pytest.mark.asyncio
async def test_document_ingestion_content_update_reembeds(db_session: AsyncSession, mock_embedding_provider):
    """Verify ingesting updated content updates the document and replaces old chunks."""
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=mock_embedding_provider)

    content_v1 = "# Dispute Rule\nDisputes must be raised within 30 days."
    doc1, chunks1 = await pipeline.ingest_document(
        title="Dispute Rule",
        source_id="internal://test-policies/dispute-v1",
        source_type="chargeback_rule",
        content=content_v1,
    )
    old_hash = doc1.content_hash
    assert len(chunks1) == 1
    assert "30 days" in chunks1[0].content

    # Ingest update with new policy window
    content_v2 = "# Dispute Rule\nDisputes must be raised within 45 days. Window extended."
    doc2, chunks2 = await pipeline.ingest_document(
        title="Dispute Rule",
        source_id="internal://test-policies/dispute-v1",
        source_type="chargeback_rule",
        content=content_v2,
    )

    assert doc2.id == doc1.id
    assert doc2.content_hash != old_hash
    assert len(chunks2) == 1
    assert "45 days" in chunks2[0].content

    # Verify old chunk was replaced
    result = await db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc1.id)
    )
    current_chunks = result.scalars().all()
    assert len(current_chunks) == 1
    assert "45 days" in current_chunks[0].content


@pytest.mark.asyncio
async def test_lexical_search_exact_technical_codes(db_session: AsyncSession, mock_embedding_provider):
    """Verify exact technical terms like return codes and dispute codes are found by lexical search."""
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=mock_embedding_provider)

    content = """# Processor Codes Specification
## ACH Return Codes
Code R01 indicates insufficient funds in customer bank account.
Code R03 indicates no account or unable to locate account.

## Card Scheme Reason Codes
Visa Reason Code 10.4 represents Other Fraud - Card-Absent Environment.
Mastercard Code 4837 represents No Cardholder Authorization.
Acquirer Reference Number ARN 74512349012348 must be tracked.
"""
    await pipeline.ingest_document(
        title="Processor Return & Dispute Codes",
        source_id="internal://specs/return-codes",
        source_type="gateway_spec",
        content=content,
    )

    service = HybridRetrievalService(db_session, embedding_provider=mock_embedding_provider)

    # 1. Search exact code R01
    results_r01 = await service.lexical_search(query_text="R01", limit=5)
    assert len(results_r01) >= 1
    assert any("R01" in r.text for r in results_r01)

    # 2. Search exact code 10.4
    results_104 = await service.lexical_search(query_text="10.4", limit=5)
    assert len(results_104) >= 1
    assert any("10.4" in r.text for r in results_104)

    # 3. Search exact technical term ARN
    results_arn = await service.lexical_search(query_text="ARN 74512349012348", limit=5)
    assert len(results_arn) >= 1
    assert any("ARN" in r.text for r in results_arn)


@pytest.mark.asyncio
async def test_semantic_search_with_model_compatibility(db_session: AsyncSession):
    """Verify semantic search queries match compatible embedding model vectors and calculate distance."""
    # Create two chunks: one with matching model, one with incompatible model
    doc = KnowledgeDocument(
        title="Compatibility Test Doc",
        source_id="internal://test/compat",
        doc_type="internal_sop",
        version="1.0",
        content_hash="dummyhash123",
        raw_content="Dummy content",
    )
    db_session.add(doc)
    await db_session.flush()

    matching_vec = [0.0] * 1536
    matching_vec[0] = 1.0  # Unit vector along axis 0

    incompatible_vec = [0.0] * 1536
    incompatible_vec[1] = 1.0

    chunk1 = DocumentChunk(
        document_id=doc.id,
        source_id=doc.source_id,
        chunk_index=0,
        content="Passage with matching model text",
        section_header="Section 1",
        token_count=10,
        embedding_model="mock-target-model",
        embedding=matching_vec,
    )
    chunk2 = DocumentChunk(
        document_id=doc.id,
        source_id=doc.source_id,
        chunk_index=1,
        content="Passage with incompatible synthetic model text",
        section_header="Section 2",
        token_count=10,
        embedding_model="synthetic_placeholder",  # must be ignored!
        embedding=incompatible_vec,
    )
    db_session.add_all([chunk1, chunk2])
    await db_session.commit()

    provider = MockEmbeddingProvider(dimension=1536, model_name="mock-target-model", fixed_vector=matching_vec)
    service = HybridRetrievalService(db_session, embedding_provider=provider)

    results = await service.semantic_search(query_vector=matching_vec, limit=5)

    assert len(results) == 1
    assert results[0].chunk_id == str(chunk1.id)
    assert results[0].embedding_model == "mock-target-model"
    # Cosine distance to itself is ~0.0, score ~1.0
    assert results[0].semantic_score is not None
    assert results[0].semantic_score > 0.99


@pytest.mark.asyncio
async def test_hybrid_search_rrf_scoring(db_session: AsyncSession, mock_embedding_provider):
    """Verify hybrid search combines lexical and semantic ranks via Reciprocal Rank Fusion."""
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=mock_embedding_provider)

    await pipeline.ingest_document(
        title="Refund Escalation SOP",
        source_id="internal://sop/refunds",
        source_type="internal_sop",
        content="""# Refund SLA Policies
## Standard Refund SLA
Standard credit card refunds take 3 to 5 business days to appear on customer statement.

## Delayed Refund Escalations
When refund exceeds 7 business days, support agent must obtain Acquirer Reference Number (ARN).
""",
    )

    service = HybridRetrievalService(db_session, embedding_provider=mock_embedding_provider)

    hybrid_results = await service.search(
        query="delayed refund ARN escalation 7 days",
        top_k=5,
        retrieval_mode="hybrid",
    )

    assert len(hybrid_results) >= 1
    top_result = hybrid_results[0]
    assert top_result.ranking is not None
    # Verify RRF fusion score is populated
    assert top_result.ranking.fusion_score is not None
    assert top_result.ranking.fusion_score > 0.0
    assert "ARN" in top_result.text or "refund" in top_result.text.lower()


@pytest.mark.asyncio
async def test_hybrid_search_fallback_when_embedding_provider_offline(db_session: AsyncSession):
    """Verify hybrid search gracefully falls back to lexical-only when embedding provider is offline."""
    offline_provider = OpenAIEmbeddingProvider(api_key="")  # unavailable
    assert not offline_provider.is_available

    # Ingest using a mock provider first
    setup_pipeline = DocumentIngestionPipeline(db_session, embedding_provider=MockEmbeddingProvider(dimension=1536))
    await setup_pipeline.ingest_document(
        title="Chargeback Window Rules",
        source_id="internal://rules/cb-window",
        source_type="chargeback_rule",
        content="# Chargeback Window\nMerchants have 30 calendar days to respond to chargebacks.",
    )

    # Retrieval service configured with offline provider
    service = HybridRetrievalService(db_session, embedding_provider=offline_provider)

    results = await service.search(
        query="calendar days to respond chargebacks",
        top_k=5,
        retrieval_mode="hybrid",
    )

    assert len(results) >= 1
    # Mode must clearly reflect lexical-only fallback
    assert results[0].retrieval_mode == "lexical"
    assert results[0].ranking.semantic_rank is None
    assert results[0].ranking.lexical_rank == 1


@pytest.mark.asyncio
async def test_hybrid_search_filtering_and_limits(db_session: AsyncSession, mock_embedding_provider):
    """Verify search respects source_type filters and top_k limits."""
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=mock_embedding_provider)

    await pipeline.ingest_document(
        title="Doc Type A",
        source_id="internal://test/type-a",
        source_type="gateway_spec",
        content="# Gateway Spec A\nTechnical details for payment gateway timeouts.",
    )
    await pipeline.ingest_document(
        title="Doc Type B",
        source_id="internal://test/type-b",
        source_type="merchant_policy",
        content="# Merchant Policy B\nMerchant rules for payment gateway timeouts.",
    )

    service = HybridRetrievalService(db_session, embedding_provider=mock_embedding_provider)

    # Filter by gateway_spec
    spec_results = await service.search(
        query="gateway timeouts",
        top_k=10,
        source_type="gateway_spec",
    )
    assert len(spec_results) >= 1
    assert all(r.source_id == "internal://test/type-a" for r in spec_results)


@pytest.mark.asyncio
async def test_grounded_citation_provenance(db_session: AsyncSession, mock_embedding_provider):
    """Verify to_citations generates reliable citations linked to stored documents and chunks."""
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=mock_embedding_provider)

    doc, chunks = await pipeline.ingest_document(
        title="Authorization Hold Policy",
        source_id="internal://policies/auth-holds",
        source_type="internal_sop",
        content="# Holds\nAuthorization holds reserve funds for up to 7 days.",
    )

    service = HybridRetrievalService(db_session, embedding_provider=mock_embedding_provider)
    search_results = await service.search(query="authorization holds reserve funds", top_k=2)

    citations = service.to_citations(search_results)
    assert len(citations) >= 1

    citation = citations[0]
    assert citation.title == "Authorization Hold Policy"
    assert citation.source_id == "internal://policies/auth-holds"
    assert citation.document_id == doc.id
    assert citation.chunk_id == chunks[0].id
    assert "reserve funds" in citation.exact_passage
    assert citation.is_synthetic_demonstration is True


@pytest.mark.asyncio
async def test_api_knowledge_search_authenticated(client: AsyncClient, db_session: AsyncSession):
    """Verify POST /api/v1/knowledge/search endpoint returns structured 200 response with auth token."""
    # 1. Create a user and access token
    test_user = User(
        email="searcher@payguard.ai",
        hashed_password="hashed_pw_xyz",
        full_name="Search User",
        role="support_agent",
        is_active=True,
    )
    db_session.add(test_user)
    await db_session.commit()

    token = create_access_token(subject=test_user.id, role=test_user.role)
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 2. Ingest a policy document
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=MockEmbeddingProvider(dimension=1536))
    await pipeline.ingest_document(
        title="Gateway Timeout API Test",
        source_id="internal://policies/api-test-timeout",
        source_type="gateway_spec",
        content="# Gateway Timeouts\nWhen a gateway times out after 30 seconds, send a status check query.",
    )

    # 3. Call search API
    payload = {
        "query": "gateway times out status check query",
        "top_k": 3,
        "retrieval_mode": "hybrid",
    }
    response = await client.post("/api/v1/knowledge/search", json=payload, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == payload["query"]
    assert data["retrieval_mode"] in ("hybrid", "lexical")
    assert len(data["results"]) >= 1
    assert data["results"][0]["title"] == "Gateway Timeout API Test"
    assert "status check query" in data["results"][0]["text"]


@pytest.mark.asyncio
async def test_api_knowledge_search_unauthenticated(client: AsyncClient):
    """Verify POST /api/v1/knowledge/search returns 401 when no token is provided."""
    payload = {"query": "any query"}
    response = await client.post("/api/v1/knowledge/search", json=payload)
    assert response.status_code == 401
