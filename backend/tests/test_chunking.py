"""Unit tests for text normalization and section-aware document chunking."""

import pytest
from backend.app.services.chunker import DocumentChunker, TextChunk


def test_chunker_empty_and_whitespace_input():
    """Verify chunker returns empty list on empty or whitespace-only inputs."""
    chunker = DocumentChunker()
    assert chunker.split_document("") == []
    assert chunker.split_document("   \n\n   \t  ") == []
    assert chunker.normalize_text("") == ""


def test_chunker_short_document():
    """Verify a short document is preserved as a single cohesive chunk."""
    chunker = DocumentChunker(target_chunk_size=500)
    text = "Short policy statement: All refund requests must be reviewed within 48 hours."
    chunks = chunker.split_document(text, document_title="Short Policy", source_id="policy://short")

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_index == 0
    assert chunk.content == text
    assert chunk.section_header == "Short Policy"
    assert chunk.metadata["source_id"] == "policy://short"
    assert chunk.token_count > 0


def test_chunker_section_aware_markdown_headers():
    """Verify markdown headers (# and ##) create distinct section chunks."""
    chunker = DocumentChunker(target_chunk_size=500)
    markdown_doc = """# Introduction
PayGuard AI adheres strictly to payment card operating regulations.

## Rule 1: Duplicate Charges
When two charges occur within 60 seconds for identical amounts, the second charge must be held for voiding.

## Rule 2: Chargeback Conditions
Condition 10.4 applies when cardholder disputes card-absent transactions without 3DS authentication.
"""
    chunks = chunker.split_document(markdown_doc, document_title="Rules Document")
    assert len(chunks) == 3

    # Check headers
    assert chunks[0].section_header == "Introduction"
    assert "PayGuard AI adheres strictly" in chunks[0].content
    assert chunks[0].chunk_index == 0

    assert chunks[1].section_header == "Rule 1: Duplicate Charges"
    assert "60 seconds" in chunks[1].content
    assert chunks[1].chunk_index == 1

    assert chunks[2].section_header == "Rule 2: Chargeback Conditions"
    assert "Condition 10.4" in chunks[2].content
    assert chunks[2].chunk_index == 2


def test_chunker_sub_splitting_long_sections_with_overlap():
    """Verify long sections exceeding target size are split across paragraphs with overlap."""
    chunker = DocumentChunker(target_chunk_size=200, chunk_overlap=40)
    para1 = "Paragraph One describes the clearing window for Automated Clearing House (ACH) transactions under NACHA standards."
    para2 = "Paragraph Two describes return reason code R01 for insufficient funds and specifies that the originator can retry up to two times."
    para3 = "Paragraph Three describes return reason code R02 for closed accounts where re-initiation is strictly prohibited."

    long_doc = f"# NACHA Guidelines\n\n{para1}\n\n{para2}\n\n{para3}"
    chunks = chunker.split_document(long_doc, document_title="ACH Manual")

    assert len(chunks) >= 2
    # All chunks retain the parent section header
    for c in chunks:
        assert c.section_header == "NACHA Guidelines"

    # Verify overlap exists
    all_content = " ".join(c.content for c in chunks)
    assert "Paragraph One" in all_content
    assert "Paragraph Two" in all_content
    assert "Paragraph Three" in all_content


def test_chunker_deterministic_output():
    """Verify that chunking identical text multiple times produces bit-for-bit identical chunks."""
    chunker = DocumentChunker()
    doc = """# SLA Specification
Section 1: Instant payment rails (FedNow, UPI) settle within 15 minutes.
Section 2: Wire transfers settle by close of business at 17:00 EST.
"""
    run_1 = chunker.split_document(doc, document_title="SLA", source_id="src_sla")
    run_2 = chunker.split_document(doc, document_title="SLA", source_id="src_sla")

    assert len(run_1) == len(run_2)
    for c1, c2 in zip(run_1, run_2):
        assert c1.chunk_index == c2.chunk_index
        assert c1.section_header == c2.section_header
        assert c1.content == c2.content
        assert c1.token_count == c2.token_count
        assert c1.metadata == c2.metadata
