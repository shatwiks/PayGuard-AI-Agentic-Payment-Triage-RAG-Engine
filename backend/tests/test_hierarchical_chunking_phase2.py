"""Phase 2 Comprehensive Test Suite: Hierarchical Chunking, Table Preservation, and Metadata Retrieval.

Validates:
1. Short documents, long documents, paragraph boundaries, overlap behavior, and oversized sections.
2. Structured Markdown table preservation: row grouping, oversized table header repetition, and exact numeric/code preservation.
3. Metadata extraction and validation: schema, condition_code, strict date validation, non-fabrication of missing fields.
4. Database parent-child hierarchy persistence and referential integrity (ON DELETE SET NULL).
5. Child-first hybrid retrieval with parent context fetching and deduplication.
6. Zero paid API calls constraint: 100% deterministic local execution.
"""

from datetime import datetime, timezone
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import create_access_token
from backend.app.models.knowledge import DocumentChunk, KnowledgeDocument
from backend.app.models.user import User
from backend.app.schemas.knowledge import KnowledgeSearchRequest, KnowledgeSearchResponse
from backend.app.services.chunker import DocumentChunker, TextChunk
from backend.app.services.embedding import MockEmbeddingProvider, OpenAIEmbeddingProvider
from backend.app.services.ingestion import DocumentIngestionPipeline
from backend.app.services.retrieval import HybridRetrievalService


@pytest.fixture
def mock_embedding_provider():
    return MockEmbeddingProvider(dimension=1536, model_name="mock-phase2-1536")


# ===========================================================================
# 1. Chunking Tests
# ===========================================================================

def test_chunker_empty_and_whitespace():
    """Verify empty or whitespace strings produce no chunks."""
    chunker = DocumentChunker()
    assert chunker.split_hierarchical("").all_chunks == []
    assert chunker.split_hierarchical("   \n\n\t  ").all_chunks == []


def test_chunker_short_document():
    """Verify a short document is preserved without unnecessary splitting."""
    chunker = DocumentChunker(target_child_chunk_size=200)
    short_text = "All refunds for credit card transactions must be initiated within 120 days."
    res = chunker.split_hierarchical(short_text, document_title="Short Policy", source_id="internal://short")

    assert len(res.parents) == 1
    assert len(res.children) == 1
    assert short_text in res.parents[0].content
    assert res.children[0].content == short_text
    assert res.children[0].parent_index == res.parents[0].chunk_index
    assert res.children[0].chunk_type == "child"
    assert res.parents[0].chunk_type == "parent"


def test_chunker_long_document_no_dropped_content():
    """Verify long multi-paragraph documents are split without dropping paragraphs."""
    chunker = DocumentChunker(
        target_parent_chunk_size=300,
        parent_chunk_overlap=30,
        target_child_chunk_size=80,
        child_chunk_overlap=15,
    )

    paragraphs = [
        f"Paragraph {i}: Detailed explanation of payment rail clearing rules for rail NACHA_{i}. "
        f"Specific return condition code R0{i % 9 + 1} requires immediate operational settlement."
        for i in range(1, 15)
    ]
    full_text = "# Complete NACHA Manual\n\n" + "\n\n".join(paragraphs)

    res = chunker.split_hierarchical(full_text, document_title="NACHA Manual")

    assert len(res.parents) >= 2
    assert len(res.children) >= 5

    # Verify no paragraph was silently dropped
    all_child_text = " ".join(c.content for c in res.children)
    for i in range(1, 15):
        assert f"Paragraph {i}:" in all_child_text


def test_chunker_paragraph_boundaries_preserved():
    """Verify chunking splits along clean paragraph breaks instead of mid-sentence."""
    chunker = DocumentChunker(target_child_chunk_size=15, child_chunk_overlap=0)
    para1 = "First paragraph details the cardholder dispute authorization timelines under Scheme rules."
    para2 = "Second paragraph details the merchant dispute response window of thirty calendar days."
    doc = f"# Section 1: Overview\n\n{para1}\n\n{para2}"

    res = chunker.split_hierarchical(doc, document_title="Dispute Timelines")
    children = res.children
    assert len(children) >= 2
    # Ensure paragraphs start and end cleanly
    assert children[0].content.startswith("First paragraph")
    assert children[1].content.startswith("Second paragraph")


def test_chunker_overlap_behavior():
    """Verify child chunk overlap retains tail tokens from the previous chunk."""
    chunker = DocumentChunker(target_child_chunk_size=30, child_chunk_overlap=10)
    paras = [
        "First long statement regarding cardholder fraud conditions in non-3DS transactions.",
        "Second subsequent statement regarding evidence submission requirements and timelines.",
    ]
    doc = "# Dispute Protocol\n\n" + "\n\n".join(paras)
    res = chunker.split_hierarchical(doc, document_title="Dispute Protocol")

    assert len(res.children) >= 2
    # Overlap implies text from first chunk appears in second chunk buffer
    first_words = set(res.children[0].content.split()[-10:])
    second_words = set(res.children[1].content.split()[:15])
    assert len(first_words.intersection(second_words)) > 0


def test_chunker_oversized_section_splitting():
    """Verify oversized sections exceeding parent target size split into multiple parent chunks."""
    chunker = DocumentChunker(target_parent_chunk_size=100, parent_chunk_overlap=20)
    long_section = "\n\n".join([f"Detailed subsection item {i} regarding gateway timeouts." for i in range(30)])
    doc = f"# Giant Section\n\n{long_section}"
    res = chunker.split_hierarchical(doc, document_title="Timeouts")

    assert len(res.parents) >= 2
    for p in res.parents:
        assert p.section_header == "Giant Section"
        assert p.chunk_type == "parent"


# ===========================================================================
# 2. Table and Structured Content Preservation Tests
# ===========================================================================

def test_table_preservation_header_and_rows_together():
    """Verify markdown table rows remain attached to headers."""
    chunker = DocumentChunker(target_child_chunk_size=300)
    table_text = """# Rail Settlement Windows

| Payment Rail | Settlement Time | Max Retry Count | SLA Window |
|---|---|---|---|
| FedNow | Instant (15s) | 0 | 99.99% |
| ACH Debit | 2-3 Business Days | 2 | 99.50% |
| Wire Transfer | Same Day 17:00 | 1 | 99.90% |
"""
    res = chunker.split_hierarchical(table_text, document_title="SLA Table Doc")
    assert len(res.children) >= 1

    table_child = res.children[0]
    assert "| Payment Rail | Settlement Time |" in table_child.content
    assert "|---|---|---|---|" in table_child.content
    assert "FedNow" in table_child.content
    assert "ACH Debit" in table_child.content
    assert "Wire Transfer" in table_child.content


def test_table_oversized_split_repeats_headers():
    """Verify oversized tables split across chunks while repeating table header and delimiter rows."""
    chunker = DocumentChunker(target_child_chunk_size=60)  # small target to force split
    rows = "\n".join([f"| Code_R{i:02d} | Reason Description {i} | Category_{i} |" for i in range(1, 15)])
    table_text = f"""# ACH Return Codes Matrix

| Return Code | Description | Severity |
|---|---|---|
{rows}
"""
    res = chunker.split_hierarchical(table_text, document_title="ACH Codes")

    # Table must be split across multiple child chunks
    assert len(res.children) >= 2

    for child in res.children:
        # Every child table chunk MUST contain the header and delimiter line
        assert "| Return Code | Description | Severity |" in child.content
        assert "|---|---|---|" in child.content


def test_exact_numeric_and_code_preservation():
    """Verify technical codes, amounts, and identifiers are not modified or truncated."""
    chunker = DocumentChunker()
    content = """# Exact Values Test
Acquirer Reference Number ARN 74512349012348572019283 was issued for transaction tx_ref_99812.
Dispute Condition 10.4 applies with fee $450.00 and refund allowance €1,250.50.
Error code R01 occurred with 3DS ECI value 05.
"""
    res = chunker.split_hierarchical(content, document_title="Exact Values")
    child = res.children[0]

    assert "74512349012348572019283" in child.content
    assert "tx_ref_99812" in child.content
    assert "Condition 10.4" in child.content
    assert "$450.00" in child.content
    assert "€1,250.50" in child.content
    assert "R01" in child.content
    assert "ECI value 05" in child.content


# ===========================================================================
# 3. Metadata Extraction & Validation Tests
# ===========================================================================

def test_metadata_extraction_valid_fields():
    """Verify payment scheme, condition code, valid date, and source provenance are extracted."""
    chunker = DocumentChunker()
    text = (
        "Visa Core Rules Dispute Condition 10.4: Other Fraud in Card-Absent environment. "
        "Effective date: 2026-06-15. Page 42."
    )
    meta = chunker.extract_metadata(text, document_title="Visa Dispute Manual", source_id="internal://visa/10-4")

    assert meta["scheme"] == "Visa"
    assert meta["condition_code"] == "10.4"
    assert meta["effective_date"] == "2026-06-15"
    assert meta["source_document"] == "Visa Dispute Manual"
    assert meta["source_id"] == "internal://visa/10-4"


def test_metadata_strict_date_validation_rejects_invalid_calendar_dates():
    """Verify invalid calendar dates (e.g., month 13 or Feb 31) are rejected and not fabricated."""
    chunker = DocumentChunker()
    text = "Policy issued on 2026-02-31 with update on 2026-13-45."
    meta = chunker.extract_metadata(text, document_title="Invalid Date Policy")

    # Neither invalid date should be accepted as effective_date
    assert "effective_date" not in meta


def test_metadata_non_fabrication():
    """Verify missing metadata fields are not invented or guessed."""
    chunker = DocumentChunker()
    text = "General operational principles for customer communication during incident triage."
    meta = chunker.extract_metadata(text, document_title="General Principles")

    assert "scheme" not in meta
    assert "condition_code" not in meta
    assert "effective_date" not in meta


# ===========================================================================
# 4. Database Persistence & Referential Integrity Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_hierarchical_persistence_and_foreign_keys(db_session: AsyncSession, mock_embedding_provider):
    """Verify parent and child chunks are persisted with foreign keys and parent-child relationships intact."""
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=mock_embedding_provider)

    doc_text = """# Visa Chargeback Rules
## Condition 10.4
Card-absent fraud where cardholder asserts no participation.

## Condition 10.5
Cardholder asserts merchant processed credit as a debit.
"""
    res = await pipeline.ingest_document(
        title="Visa Chargeback Hierarchical Policy",
        source_id="internal://visa/hierarchical-test",
        doc_type="scheme_rules",
        content=doc_text,
        hierarchical=True,
    )

    assert res.status in ("success", "lexical_only")
    assert res.parent_chunks is not None
    assert res.child_chunks is not None
    assert len(res.parent_chunks) == 2
    assert len(res.child_chunks) == 2

    # Query from database
    db_parents = (
        await db_session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == res.document_id, DocumentChunk.chunk_type == "parent")
            .order_by(DocumentChunk.chunk_index)
        )
    ).scalars().all()

    db_children = (
        await db_session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == res.document_id, DocumentChunk.chunk_type == "child")
            .order_by(DocumentChunk.chunk_index)
        )
    ).scalars().all()

    assert len(db_parents) == 2
    assert len(db_children) == 2

    # Verify each child references its parent
    parent_ids = {p.id for p in db_parents}
    for child in db_children:
        assert child.parent_chunk_id in parent_ids
        assert child.chunk_type == "child"
        assert child.content_hash is not None


@pytest.mark.asyncio
async def test_parent_deletion_referential_integrity(db_session: AsyncSession, mock_embedding_provider):
    """Verify deleting a parent chunk sets child parent_chunk_id to NULL (ON DELETE SET NULL)."""
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=mock_embedding_provider)

    res = await pipeline.ingest_document(
        title="Referential Integrity Policy",
        source_id="internal://test/ref-integrity",
        content="# Main Section\nParagraph 1.\n\nParagraph 2.",
        hierarchical=True,
    )

    parent_chunk = res.parent_chunks[0]
    child_id = res.child_chunks[0].id

    # Delete parent
    await db_session.delete(parent_chunk)
    await db_session.commit()
    db_session.expunge_all()

    # Query child freshly
    child_res = await db_session.execute(
        select(DocumentChunk).where(DocumentChunk.id == child_id)
    )
    updated_child = child_res.scalar_one_or_none()
    assert updated_child is not None
    # parent_chunk_id set to NULL without crashing
    assert updated_child.parent_chunk_id is None


@pytest.mark.asyncio
async def test_reingestion_hierarchical_idempotency(db_session: AsyncSession, mock_embedding_provider):
    """Verify re-ingesting identical content does not duplicate parent or child chunks."""
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=mock_embedding_provider)
    content = "# Static Rule\nRule description content."

    res1 = await pipeline.ingest_document(
        title="Idempotent Policy",
        source_id="internal://test/idem",
        content=content,
        hierarchical=True,
    )

    res2 = await pipeline.ingest_document(
        title="Idempotent Policy",
        source_id="internal://test/idem",
        content=content,
        hierarchical=True,
    )

    assert res1.document_id == res2.document_id
    assert res2.status == "skipped_unchanged"

    # Count database rows
    total_chunks = (
        await db_session.execute(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == res1.document_id)
        )
    ).scalar_one()

    assert total_chunks == len(res1.chunks)


# ===========================================================================
# 5. Retrieval Integration Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_child_first_retrieval_and_parent_context_fetching(db_session: AsyncSession, mock_embedding_provider):
    """Verify hybrid search retrieves child chunks and attaches surrounding parent context."""
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=mock_embedding_provider)

    policy_content = """# NACHA Operating Rules
## Return Reason Code R08
Return Code R08 indicates Payment Stopped requested by receiver.
The receiver requested their financial institution to stop payment on a specific debit entry.
"""
    await pipeline.ingest_document(
        title="NACHA Stop Payment Rules",
        source_id="internal://nacha/stop-payment",
        content=policy_content,
        hierarchical=True,
    )

    service = HybridRetrievalService(db_session, embedding_provider=mock_embedding_provider)
    search_res = await service.search(
        query="Payment Stopped receiver stop payment R08",
        top_k=3,
        include_parent_context=True,
    )

    assert len(search_res.results) >= 1
    top_result = search_res.results[0]

    # Verify primary result is child chunk
    assert top_result.chunk_type == "child"
    assert "R08" in top_result.content
    assert top_result.parent_chunk_id is not None

    # Verify parent context was attached
    assert top_result.parent_content is not None
    assert "Return Reason Code R08" in top_result.parent_content


@pytest.mark.asyncio
async def test_parent_context_deduplication(db_session: AsyncSession, mock_embedding_provider):
    """Verify multiple retrieved child chunks from the same parent share parent context without bloat."""
    small_chunker = DocumentChunker(target_child_chunk_size=15, child_chunk_overlap=0)
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=mock_embedding_provider, chunker=small_chunker)

    # Document with 1 parent section and 2 child paragraphs
    content = """# Single Large Section
Child passage one discusses EMV 3-D Secure authentication requirements.

Child passage two discusses Directory Server Transaction ID and CAVV validation.
"""
    await pipeline.ingest_document(
        title="EMV 3DS Guide",
        source_id="internal://test/3ds-guide",
        content=content,
        hierarchical=True,
    )

    service = HybridRetrievalService(db_session, embedding_provider=mock_embedding_provider)
    res = await service.search(
        query="EMV 3-D Secure Directory Server Transaction ID CAVV",
        top_k=5,
        include_parent_context=True,
    )

    assert len(res.results) >= 2
    parent_ids = {r.parent_chunk_id for r in res.results if r.parent_chunk_id}
    # Both child chunks point to the same single parent
    assert len(parent_ids) == 1
    # Both have identical parent content without redundant duplicate queries
    assert res.results[0].parent_content == res.results[1].parent_content


@pytest.mark.asyncio
async def test_metadata_filtering_by_scheme_and_condition_code(db_session: AsyncSession, mock_embedding_provider):
    """Verify search filtering by scheme and condition_code metadata."""
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=mock_embedding_provider)

    await pipeline.ingest_document(
        title="Visa 10.4 Rule",
        source_id="internal://visa/10-4",
        content="# Visa Card-Absent Fraud\nVisa Dispute Condition 10.4 details.",
        metadata={"scheme": "Visa", "condition_code": "10.4"},
        hierarchical=True,
    )

    await pipeline.ingest_document(
        title="NACHA R01 Rule",
        source_id="internal://nacha/r01",
        content="# NACHA Insufficient Funds\nNACHA Return Code R01 details.",
        metadata={"scheme": "NACHA", "condition_code": "R01"},
        hierarchical=True,
    )

    service = HybridRetrievalService(db_session, embedding_provider=mock_embedding_provider)

    # Filter by Visa
    visa_res = await service.search(query="fraud details", top_k=5, scheme="Visa")
    assert len(visa_res.results) >= 1
    assert all("Visa" in r.title or r.scheme == "Visa" for r in visa_res.results)

    # Filter by code R01
    r01_res = await service.search(query="details", top_k=5, condition_code="R01")
    assert len(r01_res.results) >= 1
    assert any("R01" in r.content for r in r01_res.results)


@pytest.mark.asyncio
async def test_lexical_fallback_when_embedding_provider_offline_hierarchical(db_session: AsyncSession):
    """Verify hierarchical search falls back to lexical retrieval when embedding provider is offline."""
    offline_provider = OpenAIEmbeddingProvider(api_key="")
    assert not offline_provider.is_available

    # Ingest using mock provider first
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=MockEmbeddingProvider(dimension=1536))
    await pipeline.ingest_document(
        title="Offline Test Policy",
        source_id="internal://test/offline",
        content="# Reversal SLA\nInstant rail reversals occur within fifteen minutes.",
        hierarchical=True,
    )

    service = HybridRetrievalService(db_session, embedding_provider=offline_provider)
    res = await service.search(query="instant rail reversals fifteen minutes", top_k=3)

    assert len(res.results) >= 1
    assert res.retrieval_mode == "lexical"
    assert res.results[0].ranking.semantic_rank is None
    assert res.results[0].ranking.lexical_rank == 1


# ===========================================================================
# 6. API Knowledge Search & Ingest Integration
# ===========================================================================

@pytest.mark.asyncio
async def test_api_hierarchical_search_response_contract(client: AsyncClient, db_session: AsyncSession):
    """Verify POST /api/v1/knowledge/search returns new hierarchical fields while preserving contract."""
    # 1. Create user and auth token
    user = User(
        email="h_searcher@payguard.ai",
        hashed_password="pw_hash_test_123",
        full_name="Hierarchical Searcher",
        role="support_agent",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(subject=user.id, role=user.role)
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Ingest document
    pipeline = DocumentIngestionPipeline(db_session, embedding_provider=MockEmbeddingProvider(dimension=1536))
    await pipeline.ingest_document(
        title="API Hierarchical Test Policy",
        source_id="internal://policies/api-hierarchical",
        content="""# Chargeback Dispute Procedures
## Evidence Requirements
Merchants must submit signed delivery proof and customer IP address logs.
""",
        hierarchical=True,
    )

    # 3. Call API
    payload = {
        "query": "signed delivery proof IP address logs",
        "top_k": 3,
        "retrieval_mode": "hybrid",
        "include_parent_context": True,
    }
    resp = await client.post("/api/v1/knowledge/search", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["query"] == payload["query"]
    assert len(data["results"]) >= 1
    top = data["results"][0]

    # Verify hierarchical & provenance fields present
    assert "chunk_id" in top
    assert "document_id" in top
    assert "parent_chunk_id" in top
    assert "chunk_type" in top
    assert "section_title" in top
    assert "parent_content" in top
    assert "content_hash" in top
    assert "metadata" in top
    assert top["title"] == "API Hierarchical Test Policy"
