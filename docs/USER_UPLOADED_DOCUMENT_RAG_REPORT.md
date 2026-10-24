# User-Uploaded Document Workflow & Evidence-Grounded RAG Engine Report

**Project:** PayGuard AI — Agentic Payment Triage & RAG Engine  
**Feature:** Phase 3: User-Uploaded Document Workflow, Multi-Tenant Ingestion & Evidence-Grounded QA  
**Audit Date:** 2026-10-24  
**Status:** **VERIFIED & OPERATIONAL (with Transparent Local Fallback Reporting)**

---

## 1. Executive Summary

PayGuard AI has been extended to support a production-grade, secure, multi-tenant user-uploaded document pipeline. Users can upload custom regulatory, compliance, and payment operations documents (PDF and TXT), which are cryptographically hashed, structurally parsed, hierarchically chunked, and indexed for evidence-grounded Question Answering and hybrid RAG retrieval.

Strict multi-tenant security guarantees that uploaded documents are strictly private to their uploading user and authorized administrators. Cross-user data isolation is enforced at every layer: document listing, metadata inspection, raw preview, grounded QA querying, and deletion.

When local or external embedding services (e.g. Ollama or OpenAI) are unavailable or unconfigured, the system never fabricates placeholder vectors or claims semantic indexing. Instead, it accurately flags the document as `lexical_only`, utilizes PostgreSQL Full-Text Search (tsvector + GIN indexing) with BM25-style ranking, and clearly discloses this status to operators in both API responses and the web UI.

---

## 2. Initial Audit & Missing Functionality Identified

Before implementing new code, an audit was performed against commit `4d17dfb` on `main`:

| Subsystem | State Before Phase 3 | Identified Deficiency |
| :--- | :--- | :--- |
| **Document Ingestion** | Ingested pre-seeded static text strings via `seed_data.py`. | No multipart file upload endpoint; no binary or streaming parser; no PDF extractor. |
| **File Formats & Validation** | None. | No magic-byte validation; no extension filtering; vulnerable to malicious file execution or extension spoofing. |
| **Content Hashing** | Basic MD5 or plain string hash in some scripts. | No cryptographic SHA-256 deduplication per tenant; duplicate uploads caused chunk duplication. |
| **Hierarchical Chunking** | Phase 2 introduced parent-child chunk structures for pre-seeded files. | Ingestion pipeline did not preserve source page numbers or bind user ownership to chunks. |
| **Multi-Tenant Isolation** | `KnowledgeDocument` lacked `uploaded_by_id` foreign key. | All documents were global/system-wide. Any authenticated user could query any document. |
| **Question Answering** | Broad query-to-chunk cosine search without citation validation. | No evidence-density verification; vulnerable to hallucinating answers when queried on absent facts. |
| **Frontend UI** | Query search box for static policy rules only. | No file upload dropzone, document list, status indicators, or grounded Q&A interface. |

---

## 3. Architecture & Technical Implementation

```
                                  USER-UPLOADED DOCUMENT PIPELINE
                                  
  [ User File (PDF / TXT) ]
             │
             ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 1. RequestBodyLimitMiddleware (Max 10 MB for /knowledge/upload)        │
  └────────────────────────────────────────────────────────────────────────┘
             │
             ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 2. DocumentParser (backend/app/services/document_parser.py)            │
  │    • Magic bytes verification (%PDF-, UTF-8/Latin-1 text probe)        │
  │    • Extension validation (.pdf, .txt)                                 │
  │    • SHA-256 cryptographic content hashing                             │
  │    • Page-by-page text extraction with pypdf                           │
  │    • Empty, corrupted, and unreadable document detection               │
  └────────────────────────────────────────────────────────────────────────┘
             │
             ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 3. Ingestion Pipeline & Safe Storage                                   │
  │    • Duplicate check via (content_hash, uploaded_by_id)                │
  │    • Safe isolated file storage: storage/uploads/{uuid}_{filename}     │
  │    • Hierarchical Chunking (split_hierarchical):                       │
  │        - Parent Chunks (sections, 1000 tokens)                         │
  │        - Child Chunks (retrieval units, 250 tokens with parent_chunk_id│
  │    • Page number tagging from extraction boundaries                    │
  │    • Embedding Provider attempt (Ollama / OpenAI / Lexical Fallback)   │
  │    • Atomic DB transaction commit with rollback & file cleanup on fail │
  └────────────────────────────────────────────────────────────────────────┘
             │
             ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 4. Grounded Question Answering Engine (document_qa.py)                 │
  │    • Multi-tenant scope resolution (user ownership guard)              │
  │    • Hybrid Retrieval (pgvector HNSW + PostgreSQL FTS GIN)             │
  │    • Substantive Keyword & Evidence Density Verification               │
  │    • Deterministic Grounded Synthesis or Clear Abstention on Absent Fact│
  │    • Exact Provenance Citations (Document, Section, Page, Chunk ID)    │
  └────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Files Changed & Added

### Backend Architecture
- [`backend/app/services/document_parser.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/app/services/document_parser.py): Secure document parsing engine using `pypdf`, magic-byte checks, page tracking, and custom domain exceptions (`EmptyDocumentException`, `CorruptedDocumentException`, `UnreadableDocumentException`, `UnsupportedDocumentTypeException`).
- [`backend/app/services/document_qa.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/app/services/document_qa.py): Grounded Question Answering service with scope enforcement, evidence-density verification, source excerpt extraction, and factual abstention logic.
- [`backend/app/services/ingestion.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/app/services/ingestion.py): Added `ingest_user_uploaded_file()` with duplicate idempotency, parent-child linking, page provenance, safe file persistence, transactional atomicity, and lexical fallback.
- [`backend/app/services/retrieval.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/app/services/retrieval.py): Updated `_apply_scope_and_doc_filters()` to filter by user ownership while keeping system seed documents discoverable.
- [`backend/app/services/chunker.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/app/services/chunker.py): Aliased `HierarchicalChunk` to `TextChunk`.
- [`backend/app/models/knowledge.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/app/models/knowledge.py): Added fields `uploaded_by_id`, `is_system`, `file_name`, `file_size_bytes`, `mime_type`, `storage_path`, `processing_status`, `embedding_status`, `error_message`, `page_count`, `chunk_count`, and compound indexes `idx_docs_uploaded_by_active`, `idx_docs_is_system_active`, and `idx_docs_content_hash_user`.
- [`backend/app/models/user.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/app/models/user.py): Added `uploaded_documents` relationship.
- [`backend/app/schemas/knowledge.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/app/schemas/knowledge.py): Added schemas `UserDocumentSummary`, `UserDocumentDetail`, `DocumentUploadResponse`, `DocumentAskRequest`, `CitedExcerptItem`, `DocumentAskResponse`.
- [`backend/app/api/knowledge.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/app/api/knowledge.py): Added routes `POST /knowledge/upload`, `GET /knowledge/documents`, `GET /knowledge/documents/{id}`, `DELETE /knowledge/documents/{id}`, and `POST /knowledge/ask`.
- [`backend/app/core/config.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/app/core/config.py): Configured `UPLOAD_MAX_FILE_SIZE_BYTES = 10_485_760` (10 MB), `UPLOAD_ALLOWED_EXTENSIONS = [".pdf", ".txt"]`, `UPLOAD_STORAGE_DIR = "./storage/uploads"`, and `RATE_LIMIT_UPLOAD_PER_MINUTE = 15`.
- [`backend/app/core/middleware.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/app/core/middleware.py): Configured `RequestBodyLimitMiddleware` to support up to 10 MB on multipart upload endpoints while keeping standard 1 MB limit on normal JSON APIs.
- [`backend/app/core/errors.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/app/core/errors.py): Aliased `NotFoundException` for consistent import hygiene.
- [`pyproject.toml`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/pyproject.toml): Added `pypdf>=6.21.2`.

### Frontend Architecture
- [`frontend/src/lib/types.ts`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/frontend/src/lib/types.ts): Added TypeScript interfaces for `UserDocumentSummary`, `UserDocumentDetail`, `DocumentUploadResponse`, `CitedExcerptItem`, `DocumentCitation`, `DocumentAskResponse`.
- [`frontend/src/lib/api.ts`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/frontend/src/lib/api.ts): Updated `request()` to properly handle `FormData` (omitting `Content-Type: application/json` so browser supplies multipart boundary). Added API methods `uploadDocument()`, `listDocuments()`, `getDocument()`, `deleteDocument()`, and `askDocumentQuestion()`.
- [`frontend/src/app/knowledge/page.tsx`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/frontend/src/app/knowledge/page.tsx): Redesigned knowledge portal into a 3-tab experience:
  1. **Upload & Manage**: Dropzone with file validation, upload progress spinner, documents table with status badges (`processed`, `lexical_only`), detail modal, and delete actions.
  2. **Grounded Q&A**: Targeted or scope-wide question answering with evidence citations and fact-abstention indicators.
  3. **Rule Explorer**: Existing transparent RAG search diagnostics.

---

## 5. Database & Migration Schema Changes

A new non-destructive Alembic migration was authored and applied to the PostgreSQL 16 database:
`alembic/versions/20261024_1130_3f8a91b2c4d5_add_user_uploaded_document_metadata.py`

### Changes to `knowledge_documents`
- `uploaded_by_id` (`UUID`, nullable, foreign key to `users.id` with `ON DELETE SET NULL`)
- `is_system` (`BOOLEAN`, default `false`, nullable=False)
- `file_name` (`VARCHAR(255)`, nullable=True)
- `file_size_bytes` (`INTEGER`, nullable=True)
- `mime_type` (`VARCHAR(64)`, nullable=True)
- `storage_path` (`VARCHAR(512)`, nullable=True)
- `processing_status` (`VARCHAR(32)`, default `'pending'`, nullable=False)
- `embedding_status` (`VARCHAR(32)`, default `'pending'`, nullable=False)
- `error_message` (`TEXT`, nullable=True)
- `page_count` (`INTEGER`, default 1, nullable=True)
- `chunk_count` (`INTEGER`, default 0, nullable=False)

### Indexes Added
- `idx_docs_uploaded_by_active` on `(uploaded_by_id, is_active)`
- `idx_docs_is_system_active` on `(is_system, is_active)`
- `idx_docs_content_hash_user` on `(content_hash, uploaded_by_id)`

**Migration Head Verified:** `3f8a91b2c4d5 (head)` applied to live PostgreSQL 16 staging database on `localhost:5434`.

---

## 6. Supported File Formats & Resource Controls

| Control | Specification | Enforcement Mechanism |
| :--- | :--- | :--- |
| **Supported Formats** | `.pdf`, `.txt` | Filename extension check AND magic-byte verification (`%PDF-`, UTF-8/Latin-1 probe). |
| **Forbidden Formats** | `.exe`, `.bin`, `.sh`, `.py`, etc. | Rejected with HTTP 415 / `UNSUPPORTED_DOCUMENT_TYPE`. |
| **Maximum File Size** | 10 MB (10,485,760 bytes) | Enforced at middleware (`RequestBodyLimitMiddleware`) and service layer (`DocumentSizeLimitException` HTTP 413). |
| **Empty File Handling** | 0 bytes or whitespace only | Rejected with HTTP 400 / `EMPTY_DOCUMENT`. |
| **Corrupted File Handling**| Unparseable PDF structure | Caught via `pypdf.errors.PdfReadError` -> HTTP 422 / `CORRUPTED_DOCUMENT`. |
| **Unreadable Scans** | PDFs without extractable text | Detected when extracted text is 0 chars -> HTTP 422 / `UNREADABLE_DOCUMENT`. |
| **Upload Rate Limit** | 15 requests / minute / IP | Token-bucket rate limiter (`rate_limit("knowledge_upload", 15)`). |
| **Safe Storage Path** | Isolated directory | `storage/uploads/{uuid.uuid4()}_{clean_basename}`. Path traversal sequences stripped. |

---

## 7. Security & Multi-Tenant Data Isolation Audit

1. **Document Ownership Enforced at DB Layer:**
   - Every user-uploaded document stores `uploaded_by_id = current_user.id` and `is_system = False`.
2. **Access Isolation (`GET /knowledge/documents`):**
   - Non-admin users querying `"uploaded"` scope receive strictly rows where `uploaded_by_id == current_user.id`.
3. **No ID Enumeration / Probing (`GET /knowledge/documents/{id}`):**
   - If User B attempts to access User A's private document by guessing its UUID, the API returns `HTTP 404 Not Found` (rather than 401 or 403), preventing existence enumeration.
4. **Isolated Grounded QA (`POST /knowledge/ask`):**
   - `_verify_and_resolve_scope()` ensures that any explicitly requested `document_ids` belong to `current_user` or are `is_system == True`. Specifying another user's document ID raises `HTTP 404 Not Found`.
5. **Deletion Protection (`DELETE /knowledge/documents/{id}`):**
   - Only the document owner or an administrator can delete a document. Unauthorized delete attempts return `HTTP 404 Not Found`.

---

## 8. Test Execution & Verified Test Counts

### Automated Backend Tests
All tests run with pytest under Python 3.14.7:

| Test Suite | Total Tests | Passed | Failed | Description |
| :--- | :---: | :---: | :---: | :--- |
| [`backend/tests/test_user_uploaded_documents.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/tests/test_user_uploaded_documents.py) | **11** | **11** | **0** | User upload workflow, PDF/TXT, corruption, duplicate idempotency, parent-child chunking, grounded QA, absent fact abstention, multi-tenant isolation, cascade deletion. |
| Existing Application Test Suites | **160** | **160** | **0** | RAG Phase 1, Phase 2, security, triage, rate limits, contracts, adversarial evaluation. |
| **Combined Test Suite** | **171** | **171** | **0** | **100% PASS across entire application.** |

### Frontend Build Verification
Executed `npm run build` in `frontend/`:
- **Turbopack Compilation:** 4.2s (Zero errors).
- **TypeScript Static Typing:** 5.2s (Zero type errors).
- **Static Page Generation:** 10/10 routes prerendered successfully.

---

## 9. Real End-to-End Acceptance Test Results

A live acceptance test script ([`backend/app/scripts/verify_user_uploaded_document_e2e.py`](file:///d:/PROJECTS/PayGuard%20AI%20Agentic%20Payment%20Triage%20&%20RAG%20Engine/backend/app/scripts/verify_user_uploaded_document_e2e.py)) was executed against the **live PostgreSQL 16 container** (`127.0.0.1:5434`) using a temporary document containing unique facts that do not exist in the seeded knowledge base:

```text
Document: ovr_8841_protocol.txt
Fact: "PayGuard Protocol OVR-8841: The mandatory settlement verification window for OVR-8841 overrides is exactly 12 minutes."
```

### Acceptance Results Table

| Acceptance Check | Expectation | Actual Live Result | Verdict |
| :--- | :--- | :--- | :---: |
| **1. Persistence** | `knowledge_documents` row saved with metadata | Document persisted (`doc_id=e4c102fc...`, size=489 B) | **PASS** |
| **2. Content Extraction** | SHA-256 hash generated and text extracted | Extracted 2 sections, content hash verified | **PASS** |
| **3. Chunk Hierarchy** | Parent and child chunks with parent linkage | 1 parent chunk, 1 child chunk (`parent_chunk_id` linked) | **PASS** |
| **4. Status Reporting** | Accurately reflect completed steps | `processing_status='processed'`, `embedding_status='lexical_only'` | **PASS** |
| **5. Unique Fact Retrieval** | Query retrieves uploaded document | Query on "12 minutes window" retrieved `ovr_8841_protocol` | **PASS** |
| **6. Grounded Answer & Citation**| Answer contains fact and cites document | `"Based on ovr_8841_protocol (Section 'SETTLEMENT WINDOW'): \"The mandatory settlement verification window for OVR-8841 overrides is exactly 12 minutes.\""` | **PASS** |
| **7. Absent Fact Abstention** | Query on absent fact cleanly abstains | Query on "interest rate penalty" returned `is_grounded=False`, citations=`[]` | **PASS** |
| **8. Multi-Tenant Denial** | Unauthorized User B cannot see, ask, or delete | User B listing: not visible. User B get/ask/delete: `HTTP 404` | **PASS** |
| **9. Duplicate Idempotency** | Re-uploading returns duplicate status, no duplicate chunks | Returned `is_duplicate=True`, preserved `doc_id`, chunk count unchanged | **PASS** |
| **10. Safe Cleanup** | Document, chunks, and temp users deleted | Deleted via API, cascading chunks removed, DB verified | **PASS** |

### Embedding Provider Status in Acceptance Test
- **Genuine local embeddings:** When tested without Ollama running and without an `OPENAI_API_KEY`, the embedding provider correctly raised `EmbeddingProviderUnavailableException`.
- **Transparent Fallback:** Rather than mocking embeddings or presenting fake vectors as real, the system accurately indexed the document with **PostgreSQL Full-Text Search (tsvector + GIN)** and marked `embedding_status = "lexical_only"`.
- **Verdict:** Retrieval operated via verified PostgreSQL FTS lexical search. Semantic retrieval via Ollama remains offline until the local Ollama daemon is started.

---

## 10. Manual Steps & Operational Notes

1. **Starting Local Ollama (Optional for Semantic Embeddings):**
   - If full semantic vector search is desired locally, install Ollama from `https://ollama.com` and run:
     ```bash
     ollama pull nomic-embed-text
     ollama serve
     ```
   - Update `.env`:
     ```env
     EMBEDDING_PROVIDER=ollama
     OLLAMA_BASE_URL=http://localhost:11434
     OLLAMA_EMBED_MODEL=nomic-embed-text
     ```
   - If Ollama is not started, the application continues to run with PostgreSQL Full-Text Search.
2. **Database Migrations:**
   - Already applied to the staging database on `localhost:5434`.
   - In any new staging environment, execute:
     ```bash
     uv run alembic upgrade head
     ```

---

## 11. Known Limitations & Recommended Next Steps

1. **OCR for Scanned Documents:**
   - Documents that are pure scanned images without text layers are detected and rejected with `UNREADABLE_DOCUMENT (HTTP 422)`. Integrating Tesseract OCR or a local vision model is recommended for Phase 4 if scanned invoices are required.
2. **DOCX / XLSX Support:**
   - Currently, `.pdf` and `.txt` are supported. Support for `.docx` and `.xlsx` can be added via `python-docx` and `openpyxl`.
3. **Chunk Level Access Control:**
   - Access control is currently enforced at the document boundary (which covers all chunks). Fine-grained per-section redaction can be added if multi-tier documents are introduced.
