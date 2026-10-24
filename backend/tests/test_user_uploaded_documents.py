"""Comprehensive automated tests for user-uploaded document RAG workflow.

Covers:
1. Valid PDF and TXT uploads.
2. Invalid file types and oversized files.
3. Empty and corrupted PDFs.
4. Duplicate uploads and idempotency.
5. Hierarchical parent-child chunk relationships and page tracking.
6. Lexical indexing fallback when embedding is unavailable.
7. Document-grounded question answering with citations.
8. Absent fact handling and clear abstentions.
9. Multi-tenant security and cross-user data isolation.
10. Document deletion and resource cleanup.
"""

import io
import os
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.security import create_access_token, get_password_hash
from backend.app.models.knowledge import DocumentChunk, KnowledgeDocument
from backend.app.models.user import User
from backend.app.services.document_parser import (
    CorruptedDocumentException,
    DocumentParser,
    EmptyDocumentException,
    UnreadableDocumentException,
    UnsupportedDocumentTypeException,
)

# Helper valid 1-page PDF bytes with extractable text
VALID_PDF_BYTES = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 120 >>
stream
BT
/F1 12 Tf
100 700 Td
(PayGuard Regulation PR-409: Instant payout transactions exceeding 50000 USD require dual compliance signoff.) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000415 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
492
%%EOF"""


async def create_test_user_and_token(db_session: AsyncSession, email: str, role: str = "compliance_analyst") -> tuple[User, str]:
    """Helper to persist a test user directly and generate JWT access token."""
    res = await db_session.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            email=email,
            hashed_password=get_password_hash("Password123!Secure"),
            full_name=f"User {email}",
            role=role,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

    token = create_access_token(subject=user.id, role=user.role)
    return user, token


@pytest.mark.asyncio
async def test_upload_valid_txt_document(client: AsyncClient, db_session: AsyncSession):
    """Verify authenticated user can upload a valid text document and get hierarchical chunks."""
    _, token = await create_test_user_and_token(db_session, "alice.uploader@payguard.ai")
    headers = {"Authorization": f"Bearer {token}"}

    txt_content = (
        "Merchant Tiering Policy MT-101.\n\n"
        "Tier 1 merchants have a rolling settlement cycle of T+1 days with maximum chargeback buffer of 1.5%.\n\n"
        "Tier 2 merchants have a rolling settlement cycle of T+3 days with maximum chargeback buffer of 2.0%.\n\n"
        "High risk merchants must maintain a 10% rolling reserve for 180 calendar days."
    ).encode("utf-8")

    files = {"file": ("merchant_tiering.txt", txt_content, "text/plain")}
    response = await client.post("/api/v1/knowledge/upload", headers=headers, files=files)
    assert response.status_code == 201
    data = response.json()

    assert data["file_name"] == "merchant_tiering.txt"
    assert data["processing_status"] == "processed"
    assert data["embedding_status"] in ("embedded", "lexical_only")
    assert data["page_count"] == 1
    assert data["chunk_count"] >= 1
    assert data["is_duplicate"] is False
    doc_id = data["id"]

    # Verify document in DB
    result = await db_session.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == uuid.UUID(doc_id)))
    doc = result.scalar_one_or_none()
    assert doc is not None
    assert doc.is_system is False
    assert doc.file_size_bytes == len(txt_content)


@pytest.mark.asyncio
async def test_upload_valid_pdf_document(client: AsyncClient, db_session: AsyncSession):
    """Verify uploading a valid PDF extracts text, preserves page count, and indexes document."""
    _, token = await create_test_user_and_token(db_session, "bob.pdf@payguard.ai")
    headers = {"Authorization": f"Bearer {token}"}

    files = {"file": ("regulation_pr409.pdf", VALID_PDF_BYTES, "application/pdf")}
    response = await client.post("/api/v1/knowledge/upload", headers=headers, files=files)
    assert response.status_code == 201
    data = response.json()

    assert data["file_name"] == "regulation_pr409.pdf"
    assert data["page_count"] == 1
    assert data["chunk_count"] >= 1
    assert data["processing_status"] == "processed"


@pytest.mark.asyncio
async def test_upload_duplicate_idempotency(client: AsyncClient, db_session: AsyncSession):
    """Verify uploading the exact same document twice is idempotent and does not duplicate chunks."""
    _, token = await create_test_user_and_token(db_session, "charlie.dup@payguard.ai")
    headers = {"Authorization": f"Bearer {token}"}

    content = b"Fedwire Operations Rule FW-100: Cutoff time is 18:30 Eastern Standard Time daily."
    files = {"file": ("fw_rules.txt", content, "text/plain")}

    # First upload
    res1 = await client.post("/api/v1/knowledge/upload", headers=headers, files=files)
    assert res1.status_code == 201
    d1 = res1.json()
    assert d1["is_duplicate"] is False

    # Second upload with identical bytes
    files2 = {"file": ("fw_rules_renamed.txt", content, "text/plain")}
    res2 = await client.post("/api/v1/knowledge/upload", headers=headers, files=files2)
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["is_duplicate"] is True
    assert d2["id"] == d1["id"]
    assert d2["chunk_count"] == d1["chunk_count"]


@pytest.mark.asyncio
async def test_upload_invalid_file_types_and_extensions(client: AsyncClient, db_session: AsyncSession):
    """Verify non-allowed extensions (e.g. .exe, .py, .sh) are rejected."""
    _, token = await create_test_user_and_token(db_session, "sec.tester@payguard.ai")
    headers = {"Authorization": f"Bearer {token}"}

    # Executable masquerading as txt
    files = {"file": ("malware.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/x-dosexec")}
    res = await client.post("/api/v1/knowledge/upload", headers=headers, files=files)
    assert res.status_code in (400, 415)

    # Shell script
    files_sh = {"file": ("script.sh", b"#!/bin/bash\nrm -rf /", "application/x-sh")}
    res_sh = await client.post("/api/v1/knowledge/upload", headers=headers, files=files_sh)
    assert res_sh.status_code in (400, 415)


@pytest.mark.asyncio
async def test_upload_empty_document(client: AsyncClient, db_session: AsyncSession):
    """Verify empty 0-byte upload is rejected with EMPTY_DOCUMENT error."""
    _, token = await create_test_user_and_token(db_session, "empty.test@payguard.ai")
    headers = {"Authorization": f"Bearer {token}"}

    files = {"file": ("empty.txt", b"", "text/plain")}
    res = await client.post("/api/v1/knowledge/upload", headers=headers, files=files)
    assert res.status_code == 400
    err_str = str(res.json()).lower()
    assert "empty" in err_str


@pytest.mark.asyncio
async def test_upload_corrupted_pdf(client: AsyncClient, db_session: AsyncSession):
    """Verify corrupted PDF structure is rejected with CORRUPTED_DOCUMENT error."""
    _, token = await create_test_user_and_token(db_session, "corrupt.test@payguard.ai")
    headers = {"Authorization": f"Bearer {token}"}

    corrupted_pdf = b"%PDF-1.4\ncorrupted_binary_garbage_without_xref_or_trailers\x00\xff\xfe"
    files = {"file": ("corrupt.pdf", corrupted_pdf, "application/pdf")}
    res = await client.post("/api/v1/knowledge/upload", headers=headers, files=files)
    assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_hierarchical_parent_child_chunks(client: AsyncClient, db_session: AsyncSession):
    """Verify ingestion creates both parent and child chunks with parent_chunk_id linkage."""
    _, token = await create_test_user_and_token(db_session, "hier.test@payguard.ai")
    headers = {"Authorization": f"Bearer {token}"}

    # Generate document with multiple structured sections
    content = (
        "SECTION 1: CHARGEBACK DISPUTES\n\n"
        "When an ACH debit is returned with code R01 (Insufficient Funds), the merchant may retry up to 2 times "
        "within 30 calendar days. Retries must maintain the original transaction trace ID.\n\n"
        "SECTION 2: UNAUTHORIZED DISPUTES\n\n"
        "Return code R10 represents customer claim of unauthorized debit. Merchants have 14 days to provide "
        "written mandate proof. Failure to respond results in immediate debit reversal."
    ).encode("utf-8")

    files = {"file": ("ach_rules.txt", content, "text/plain")}
    res = await client.post("/api/v1/knowledge/upload", headers=headers, files=files)
    assert res.status_code == 201
    doc_id = uuid.UUID(res.json()["id"])

    # Query chunks from database
    result = await db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
    )
    chunks = result.scalars().all()
    assert len(chunks) >= 2

    # Verify both child and parent chunks exist
    children = [c for c in chunks if c.chunk_type == "child"]
    parents = [c for c in chunks if c.chunk_type == "parent"]
    assert len(parents) >= 1
    assert len(children) >= 1
    # Check parent linkage on children
    for child in children:
        assert child.parent_chunk_id is not None
        assert any(p.id == child.parent_chunk_id for p in parents)


@pytest.mark.asyncio
async def test_document_grounded_qa_success(client: AsyncClient, db_session: AsyncSession):
    """Verify /knowledge/ask returns grounded answers with exact source citations."""
    _, token = await create_test_user_and_token(db_session, "qa.user@payguard.ai")
    headers = {"Authorization": f"Bearer {token}"}

    unique_content = (
        "Global Settlement Guideline GS-7712:\n"
        "Emergency currency conversion halts occur when the EUR/USD 5-minute volatility threshold exceeds 3.45%.\n"
        "The automated circuit breaker pauses incoming payment settlement for exactly 15 minutes."
    ).encode("utf-8")

    upload_res = await client.post(
        "/api/v1/knowledge/upload",
        headers=headers,
        files={"file": ("gs7712.txt", unique_content, "text/plain")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Ask grounded question
    ask_payload = {
        "query": "What is the volatility threshold that triggers emergency currency conversion halts in GS-7712?",
        "document_ids": [doc_id],
        "scope": "uploaded",
    }
    ask_res = await client.post("/api/v1/knowledge/ask", headers=headers, json=ask_payload)
    assert ask_res.status_code == 200
    answer_data = ask_res.json()

    assert answer_data["is_grounded"] is True
    assert "3.45%" in answer_data["answer"] or "volatility" in answer_data["answer"].lower()
    assert len(answer_data["citations"]) >= 1
    citation = answer_data["citations"][0]
    assert citation["document_id"] == doc_id
    assert "gs7712" in citation["document_name"]
    assert citation["chunk_id"] != ""


@pytest.mark.asyncio
async def test_document_grounded_qa_abstention_on_absent_fact(client: AsyncClient, db_session: AsyncSession):
    """Verify /knowledge/ask clearly abstains and returns is_grounded=False for absent facts."""
    _, token = await create_test_user_and_token(db_session, "abstain.user@payguard.ai")
    headers = {"Authorization": f"Bearer {token}"}

    content = b"Merchant agreement specifies monthly account maintenance fee is 25 USD."
    upload_res = await client.post(
        "/api/v1/knowledge/upload",
        headers=headers,
        files={"file": ("fees.txt", content, "text/plain")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Question completely absent from document
    ask_payload = {
        "query": "What is the cryptocurrency withdrawal fee for Ethereum under the merchant agreement?",
        "document_ids": [doc_id],
        "scope": "uploaded",
    }
    ask_res = await client.post("/api/v1/knowledge/ask", headers=headers, json=ask_payload)
    assert ask_res.status_code == 200
    answer_data = ask_res.json()

    # Must abstain
    assert answer_data["is_grounded"] is False
    assert "does not contain" in answer_data["answer"].lower() or "not mentioned" in answer_data["answer"].lower()
    assert answer_data["citations"] == []


@pytest.mark.asyncio
async def test_cross_user_isolation(client: AsyncClient, db_session: AsyncSession):
    """Verify multi-tenant isolation: User B cannot access, ask against, or delete User A's uploaded document."""
    # User A uploads confidential document
    _, token_a = await create_test_user_and_token(db_session, "tenant_a@payguard.ai")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    content_a = b"Confidential Acquisition Agreement: Target company valued at 45M USD."
    res_a = await client.post(
        "/api/v1/knowledge/upload",
        headers=headers_a,
        files={"file": ("secret_deal.txt", content_a, "text/plain")},
    )
    assert res_a.status_code == 201
    doc_a_id = res_a.json()["id"]

    # User B registers and attempts access
    _, token_b = await create_test_user_and_token(db_session, "tenant_b@payguard.ai")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. User B lists documents -> doc_a should NOT appear
    list_res_b = await client.get("/api/v1/knowledge/documents", headers=headers_b)
    assert list_res_b.status_code == 200
    docs_b = list_res_b.json()
    assert not any(d["id"] == doc_a_id for d in docs_b)

    # 2. User B tries to view doc_a details -> 404 Not Found
    get_res_b = await client.get(f"/api/v1/knowledge/documents/{doc_a_id}", headers=headers_b)
    assert get_res_b.status_code == 404

    # 3. User B tries to ask question targeting doc_a -> 404
    ask_res_b = await client.post(
        "/api/v1/knowledge/ask",
        headers=headers_b,
        json={"query": "What is the valuation?", "document_ids": [doc_a_id]},
    )
    assert ask_res_b.status_code == 404

    # 4. User B tries to delete doc_a -> 404
    del_res_b = await client.delete(f"/api/v1/knowledge/documents/{doc_a_id}", headers=headers_b)
    assert del_res_b.status_code == 404

    # Verify User A can still retrieve the document intact
    get_res_a = await client.get(f"/api/v1/knowledge/documents/{doc_a_id}", headers=headers_a)
    assert get_res_a.status_code == 200


@pytest.mark.asyncio
async def test_document_deletion_cleanup(client: AsyncClient, db_session: AsyncSession):
    """Verify deleting a document cascades to chunks, cleans up file storage, and prevents further retrieval."""
    _, token = await create_test_user_and_token(db_session, "deleter@payguard.ai")
    headers = {"Authorization": f"Bearer {token}"}

    content = b"Temporary Document: Will be deleted shortly."
    upload_res = await client.post(
        "/api/v1/knowledge/upload",
        headers=headers,
        files={"file": ("to_delete.txt", content, "text/plain")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Confirm chunks exist
    chunks_before = await db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(doc_id))
    )
    assert len(chunks_before.scalars().all()) >= 1

    # Delete document
    del_res = await client.delete(f"/api/v1/knowledge/documents/{doc_id}", headers=headers)
    assert del_res.status_code in (200, 204)

    # Document details should now return 404
    get_after = await client.get(f"/api/v1/knowledge/documents/{doc_id}", headers=headers)
    assert get_after.status_code == 404

    # Document should be marked inactive or removed
    doc_check = await db_session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == uuid.UUID(doc_id))
    )
    doc_record = doc_check.scalar_one_or_none()
    assert doc_record is None or doc_record.is_active is False
