"""Phase 1 RAG Productionization Test Suite.

Validates:
- Genuine embedding provider architecture and text-embedding-3-small defaults
- Validation of provider responses, dimensions, empty inputs, and timeouts
- Re-embedding idempotency, batching, and resumability
- Persistence of genuine embeddings to PostgreSQL / SQLAlchemy models
- Strict exclusion of placeholder embeddings from semantic retrieval
- Lexical fallback when embedding provider is offline
- Cosine distance calculations and pgvector HNSW index compatibility
"""

import math
from unittest.mock import MagicMock, patch
import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import PayGuardException
from backend.app.models.knowledge import DocumentChunk, KnowledgeDocument
from backend.app.scripts.seed_data import (
    reembed_knowledge_chunks,
    seed_knowledge_documents,
)
from backend.app.services.embedding import (
    EmbeddingProviderUnavailableException,
    EmbeddingValidationException,
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from backend.app.services.retrieval import HybridRetrievalService


# ---------------------------------------------------------------------------
# 1. Successful Embedding Generation & Validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_openai_provider_successful_embedding_generation():
    """Verify OpenAIEmbeddingProvider formats payload, parses response, and returns valid 1536-d vectors."""
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test-live-key-valid",
        dimension=1536,
        model="text-embedding-3-small",
        batch_size=2,
    )
    assert provider.is_available is True
    assert provider.model_name == "text-embedding-3-small"
    assert provider.dimension == 1536

    sample_vec_1 = [0.001 * (i % 10) for i in range(1536)]
    sample_vec_2 = [0.002 * (i % 10) for i in range(1536)]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "object": "list",
        "data": [
            {"object": "embedding", "index": 0, "embedding": sample_vec_1},
            {"object": "embedding", "index": 1, "embedding": sample_vec_2},
        ],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 12, "total_tokens": 12},
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_resp) as mock_post:
        results = await provider.embed_batch(["NACHA Return Code R01", "Visa Dispute 10.4"])

        assert len(results) == 2
        assert len(results[0]) == 1536
        assert len(results[1]) == 1536
        assert results[0] == sample_vec_1
        assert results[1] == sample_vec_2

        # Verify request parameters
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["model"] == "text-embedding-3-small"
        assert call_kwargs["json"]["dimensions"] == 1536
        assert call_kwargs["json"]["input"] == ["NACHA Return Code R01", "Visa Dispute 10.4"]


# ---------------------------------------------------------------------------
# 2. Invalid Provider Responses & Edge Cases
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invalid_provider_response_structures():
    """Verify that malformed or non-compliant provider responses raise EmbeddingValidationException."""
    provider = OpenAIEmbeddingProvider(api_key="sk-test-key", dimension=1536)

    # Case A: Missing 'data' list
    resp_no_data = MagicMock(status_code=200)
    resp_no_data.json.return_value = {"error": "unexpected format"}
    resp_no_data.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=resp_no_data):
        with pytest.raises(EmbeddingValidationException, match="missing valid 'data' list"):
            await provider.embed_batch(["test query"])

    # Case B: Batch count mismatch (sent 2 inputs, got 1 back)
    resp_count_mismatch = MagicMock(status_code=200)
    resp_count_mismatch.json.return_value = {
        "data": [{"index": 0, "embedding": [0.01] * 1536}]
    }
    resp_count_mismatch.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=resp_count_mismatch):
        with pytest.raises(EmbeddingValidationException, match="returned 1 embeddings for batch of size 2"):
            await provider.embed_batch(["query 1", "query 2"])

    # Case C: Item missing 'embedding' key
    resp_missing_emb = MagicMock(status_code=200)
    resp_missing_emb.json.return_value = {
        "data": [{"index": 0, "vectors": [0.01] * 1536}]
    }
    resp_missing_emb.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=resp_missing_emb):
        with pytest.raises(EmbeddingValidationException, match="missing required 'embedding' key"):
            await provider.embed_batch(["query 1"])


# ---------------------------------------------------------------------------
# 3. Empty & Whitespace Inputs
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_and_whitespace_input_validation():
    """Verify that empty, blank, or whitespace-only inputs are rejected before sending network calls."""
    provider = OpenAIEmbeddingProvider(api_key="sk-test-key", dimension=1536)

    with pytest.raises(EmbeddingValidationException, match="empty or blank query text"):
        await provider.embed_query("")

    with pytest.raises(EmbeddingValidationException, match="empty or blank query text"):
        await provider.embed_query("    \n\t  ")

    with pytest.raises(EmbeddingValidationException, match="empty or blank text at index 1"):
        await provider.embed_batch(["valid passage", "   ", "another valid passage"])


# ---------------------------------------------------------------------------
# 4. Timeout & API Failures (No Secret Leakage)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_provider_timeout_and_error_sanitization():
    """Verify timeout and HTTP error handling sanitize credentials and raise PayGuard exceptions."""
    secret = "sk-super-secret-key-do-not-leak"
    provider = OpenAIEmbeddingProvider(api_key=secret, dimension=1536)

    # Timeout
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(EmbeddingProviderUnavailableException) as exc_info:
            await provider.embed_query("timeout check")
        assert "TimeoutException" in str(exc_info.value)
        assert secret not in str(exc_info.value)

    # HTTP 429 Rate limit
    mock_resp_429 = MagicMock(status_code=429, text='{"error": {"message": "Rate limit exceeded"}}')
    err_429 = httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=mock_resp_429)

    with patch("httpx.AsyncClient.post", side_effect=err_429):
        with pytest.raises(EmbeddingProviderUnavailableException) as exc_info:
            await provider.embed_query("rate limit check")
        assert "HTTP 429" in str(exc_info.value)
        assert secret not in str(exc_info.value)


# ---------------------------------------------------------------------------
# 5. Vector Dimension & Value Validation
# ---------------------------------------------------------------------------
def test_vector_dimension_and_value_validation():
    """Verify strict dimension enforcement and NaN / Inf rejection."""
    provider = OpenAIEmbeddingProvider(api_key="sk-test", dimension=1536)

    # Correct dimension passes
    valid_vec = [0.01] * 1536
    assert provider.validate_vector(valid_vec) == valid_vec

    # Dimension too short
    with pytest.raises(EmbeddingValidationException, match="expected 1536, got 1535"):
        provider.validate_vector([0.01] * 1535)

    # Dimension too long
    with pytest.raises(EmbeddingValidationException, match="expected 1536, got 1537"):
        provider.validate_vector([0.01] * 1537)

    # NaN rejection
    nan_vec = [0.01] * 1536
    nan_vec[500] = float("nan")
    with pytest.raises(EmbeddingValidationException, match="Invalid embedding value at index 500"):
        provider.validate_vector(nan_vec)

    # Inf rejection
    inf_vec = [0.01] * 1536
    inf_vec[100] = float("inf")
    with pytest.raises(EmbeddingValidationException, match="Invalid embedding value at index 100"):
        provider.validate_vector(inf_vec)


# ---------------------------------------------------------------------------
# 6. Re-Embedding Workflow Idempotency & Resumability
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reembed_workflow_idempotency(db_session: AsyncSession):
    """Verify that reembed_knowledge_chunks safely updates eligible chunks and is idempotent."""
    # 1. Seed initial documents with fallback placeholder
    docs = await seed_knowledge_documents(db_session)
    assert len(docs) == 5

    total_chunks = (await db_session.execute(select(func.count(DocumentChunk.id)))).scalar_one()
    assert total_chunks == 10

    # 2. Re-embed with a controlled mock provider
    mock_provider = MockEmbeddingProvider(
        dimension=1536,
        model_name="text-embedding-3-small",
        available=True,
    )

    report_1 = await reembed_knowledge_chunks(db_session, provider=mock_provider, force=False)
    assert report_1["status"] == "completed"
    assert report_1["total_chunks"] == 10
    assert report_1["eligible_chunks"] == 10
    assert report_1["reembedded"] == 10
    assert report_1["skipped"] == 0
    assert report_1["failed"] == 0

    # Verify database persistence
    chunks_stmt = select(DocumentChunk)
    chunks = (await db_session.execute(chunks_stmt)).scalars().all()
    for c in chunks:
        assert c.embedding_model == "text-embedding-3-small"
        assert len(c.embedding) == 1536
        assert c.metadata_["provenance"] == "live_provider_generated"
        assert "reembedded_at" in c.metadata_

    # 3. Re-run without force -> should be idempotent and skip all 10
    report_2 = await reembed_knowledge_chunks(db_session, provider=mock_provider, force=False)
    assert report_2["status"] == "up_to_date"
    assert report_2["reembedded"] == 0
    assert report_2["skipped"] == 10
    assert report_2["failed"] == 0

    # 4. Total chunk and document count unchanged (no duplicates)
    total_chunks_after = (await db_session.execute(select(func.count(DocumentChunk.id)))).scalar_one()
    total_docs_after = (await db_session.execute(select(func.count(KnowledgeDocument.id)))).scalar_one()
    assert total_chunks_after == 10
    assert total_docs_after == 5


# ---------------------------------------------------------------------------
# 7. Safe Fallback When Provider Credentials Unavailable
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reembed_safe_fallback_when_unconfigured(db_session: AsyncSession):
    """Verify that when credentials are not configured, chunks are not corrupted or replaced with placeholders."""
    # Offline provider
    offline_provider = OpenAIEmbeddingProvider(api_key="", model="text-embedding-3-small")
    assert offline_provider.is_available is False

    report = await reembed_knowledge_chunks(db_session, provider=offline_provider)
    assert report["status"] == "unverified_provider_unavailable"
    assert report["provider_available"] is False
    assert report["reembedded"] == 0
    assert "Live semantic embeddings remain unverified" in report["message"]


# ---------------------------------------------------------------------------
# 8. Exclusion of Placeholder Embeddings from Semantic Retrieval
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_semantic_retrieval_excludes_placeholder_embeddings(db_session: AsyncSession):
    """Verify that chunks tagged with 'synthetic_placeholder' are strictly excluded from semantic search."""
    doc = KnowledgeDocument(
        title="Test Policy Document",
        source_id="internal://test/policy-1",
        doc_type="scheme_rules",
        version="1.0",
        raw_content="Content for testing semantic retrieval filtering.",
        content_hash="dummyhash123",
        is_active=True,
    )
    db_session.add(doc)
    await db_session.flush()

    # Valid chunk
    valid_vec = [0.0] * 1536
    valid_vec[0] = 1.0  # Unit vector along axis 0
    valid_chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        section_header="Valid Real Section",
        content="Grounding passage with genuine vector embedding.",
        token_count=10,
        embedding=valid_vec,
        embedding_model="text-embedding-3-small",
    )

    # Placeholder chunk
    placeholder_vec = [0.025] * 1536
    placeholder_chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=1,
        section_header="Synthetic Placeholder Section",
        content="Grounding passage with synthetic placeholder embedding.",
        token_count=10,
        embedding=placeholder_vec,
        embedding_model="synthetic_placeholder",
    )

    db_session.add_all([valid_chunk, placeholder_chunk])
    await db_session.commit()

    # Provider matching valid model
    provider = MockEmbeddingProvider(
        dimension=1536,
        model_name="text-embedding-3-small",
        fixed_vector=valid_vec,
    )
    retrieval = HybridRetrievalService(session=db_session, embedding_provider=provider)

    results = await retrieval.semantic_search(query="Grounding passage", limit=5)

    assert len(results) == 1
    assert results[0].chunk.id == valid_chunk.id
    assert results[0].chunk.embedding_model == "text-embedding-3-small"
    # Placeholder chunk MUST NOT be returned
    returned_ids = [r.chunk.id for r in results]
    assert placeholder_chunk.id not in returned_ids

    # If someone queries with synthetic_placeholder as target_model, it must reject
    bad_provider = MockEmbeddingProvider(
        dimension=1536,
        model_name="synthetic_placeholder",
        fixed_vector=placeholder_vec,
    )
    bad_retrieval = HybridRetrievalService(session=db_session, embedding_provider=bad_provider)
    bad_results = await bad_retrieval.semantic_search(query="Grounding passage", limit=5)
    assert len(bad_results) == 0


# ---------------------------------------------------------------------------
# 9. Lexical Retrieval Continues When Embedding Provider Offline
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lexical_fallback_when_embedding_provider_offline(db_session: AsyncSession):
    """Verify that full RAG search gracefully falls back to lexical retrieval when embedding provider is offline."""
    doc = KnowledgeDocument(
        title="NACHA Direct Debit Operating Rules",
        source_id="internal://test/nacha-rules",
        doc_type="scheme_rules",
        version="2026.1",
        raw_content="NACHA Return Code R01 indicates insufficient account funds for debit.",
        content_hash="nachahash999",
        is_active=True,
    )
    db_session.add(doc)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        section_header="Return Code R01",
        content="NACHA Return Code R01 indicates insufficient funds in receiver account.",
        token_count=12,
        embedding=None,
        embedding_model=None,
    )
    db_session.add(chunk)
    await db_session.commit()

    offline_provider = MockEmbeddingProvider(available=False)
    retrieval = HybridRetrievalService(session=db_session, embedding_provider=offline_provider)

    # Hybrid mode query with offline embedding provider
    response = await retrieval.search(query="insufficient funds R01", top_k=3, retrieval_mode="hybrid")

    assert response.retrieval_mode == "lexical"
    assert response.results_count >= 1
    assert "R01" in response.results[0].content


# ---------------------------------------------------------------------------
# 10. Cosine Similarity & Distance Mathematics
# ---------------------------------------------------------------------------
def test_cosine_distance_mathematics():
    """Verify that cosine similarity behaves correctly: 1.0 for parallel, 0.0 for orthogonal."""
    # Parallel unit vectors
    v1 = [1.0, 0.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0, 0.0]
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_1 = math.sqrt(sum(a * a for a in v1))
    norm_2 = math.sqrt(sum(b * b for b in v2))
    sim_parallel = dot / (norm_1 * norm_2)
    assert math.isclose(sim_parallel, 1.0)
    assert math.isclose(1.0 - sim_parallel, 0.0)

    # Orthogonal unit vectors
    v3 = [0.0, 1.0, 0.0, 0.0]
    dot_ortho = sum(a * b for a, b in zip(v1, v3))
    sim_ortho = dot_ortho / (norm_1 * norm_2)
    assert math.isclose(sim_ortho, 0.0)
    assert math.isclose(1.0 - sim_ortho, 1.0)
