# PayGuard AI — Phase 2: Hierarchical Chunking and Metadata Report
**Production Engineering Report: Parent-Child Chunking, Table Preservation, Structured Metadata, and Context-Aware Retrieval**

---

## 1. Executive Summary

Phase 2 of the PayGuard AI RAG Productionization roadmap introduces production-quality hierarchical document chunking and metadata-aware retrieval. Building directly on Phase 1's embedding provider abstraction, placeholder exclusion, and PostgreSQL HNSW vector indexing, this phase upgrades the document ingestion pipeline from a flat, unlinked text-splitter into a two-tiered parent-child chunking architecture.

Key achievements in Phase 2:
- **Parent-Child Chunking Architecture:** Implemented two-tier hierarchical chunking (configurable parent target: 1,000 tokens / 100 overlap; child target: 200 tokens / 30 overlap) with section-header extraction and paragraph boundary preservation.
- **Table Preservation Engine:** Structured Markdown tables are detected and preserved intact. Oversized tables exceeding child chunk limits are split along row boundaries with table header and separator rows replicated on every slice, preventing orphaned data rows and retaining technical codes (`10.4`, `R01`, `$149.00`, ARN `74512349012348572019283`).
- **Structured Metadata & Schema Enhancement:** Extended `document_chunks` with `parent_chunk_id` (foreign key to `document_chunks.id` with `ON DELETE SET NULL`), `chunk_type` (`"parent"`, `"child"`, `"standalone"`), `section_title`, and SHA-256 `content_hash`. Extracted and validated metadata (`scheme`, `condition_code`, `effective_date`, `page_number`, `source_document`) with strict calendar validation.
- **Non-Destructive Alembic Migration (`0e464616411f`):** Safely migrated the live PostgreSQL 16 database while preserving existing document records, the Phase 1 pgvector HNSW index (`idx_document_chunks_embedding_hnsw`), and the full-text search GIN index (`idx_document_chunks_tsv`).
- **Context-Aware Retrieval:** Search queries target focused child chunks to maximize semantic and lexical precision, while batch-fetching and attaching surrounding parent context (`parent_content`) with parent deduplication.
- **Backward-Compatible Search API:** Updated `/api/v1/knowledge/search` to optionally expose parent context, section titles, and structured metadata without breaking existing frontend consumers. Next.js production build (`npm run build`) succeeded with 0 errors across all 10 routes.
- **Resumable Backfill:** Updated `seed_data.py` with `--hierarchical` backfill support. Seeded 5 authoritative payment documents into 10 parent chunks and 10 child chunks with 0 missing relationships and 0 duplicates.
- **Testing & Verification:** 160/160 backend tests passing (including 20 new Phase 2 unit tests and 7 live PostgreSQL integration tests). Zero paid API calls were made.

---

## 2. Initial Implementation Audit

Prior to making changes, the repository was audited across all RAG subsystems:

| Component | Pre-Phase 2 Implementation | Audit Findings & Phase 2 Requirements |
|---|---|---|
| **Document Ingestion & Chunking** | `DocumentChunker.split_document` in `backend/app/services/chunker.py` | Performed flat text splitting using naive character-based approximation (`target_chunk_size=1000`, `overlap=100`). Document sections and tables were flattened into single chunks without hierarchy. |
| **Database Schema** | `DocumentChunk` model in `backend/app/models/knowledge.py` | Table contained `id`, `document_id`, `chunk_index`, `section_header`, `content`, `token_count`, `embedding`, `embedding_model`, `tsv`, `metadata`, `created_at`. No `parent_chunk_id`, no `chunk_type`, and no `content_hash`. |
| **Alembic History** | Revision `1876c4722542` (Phase 1 HNSW index) | Live PostgreSQL database head was at `1876c4722542`. Migration must be non-destructive, preserving existing data and indexes. |
| **Embedding Provider** | `backend/app/services/embedding.py` | `OpenAIEmbeddingProvider` and `MockEmbeddingProvider`. Synthetic placeholder embeddings tagged with `synthetic_placeholder`. Must not be mixed with genuine models. |
| **Retrieval & Hybrid Ranking** | `HybridRetrievalService` in `backend/app/services/retrieval.py` | Searched all chunks indiscriminately. Did not distinguish between parents and children. Lacked parent context retrieval. |
| **Knowledge Search API** | `backend/app/api/knowledge.py` & `backend/app/schemas/knowledge.py` | `/api/v1/knowledge/search` returned `SearchResultItem` containing `id`, `document_id`, `document_title`, `section_header`, `content`, `similarity_score`, `metadata`. Backward compatibility required. |
| **Seed & Backfill Script** | `backend/app/scripts/seed_data.py` | Ingested documents using the flat chunker and optionally re-embedded. Needed upgrade to ingest hierarchical parent-child structures deterministically. |

---

## 3. Files Changed

1. **`backend/app/core/config.py`**
   - Added hierarchical chunking configuration parameters:
     - `CHUNK_PARENT_SIZE = 1000` (target tokens for parent sections)
     - `CHUNK_PARENT_OVERLAP = 100` (token overlap between parent sections)
     - `CHUNK_CHILD_SIZE = 200` (target tokens for child retrieval units)
     - `CHUNK_CHILD_OVERLAP = 30` (token overlap between child chunks)
     - `CHUNK_TABLE_AWARE_ENABLED = True` (flag to preserve Markdown tables)

2. **`backend/app/models/knowledge.py`**
   - Added columns to `DocumentChunk`:
     - `parent_chunk_id`: `GUID` foreign key referencing `document_chunks.id` with `ondelete="SET NULL"`.
     - `chunk_type`: `VARCHAR(32)` (`"parent"`, `"child"`, `"standalone"`), default `"child"`.
     - `section_title`: `VARCHAR(255)`, nullable.
     - `content_hash`: `VARCHAR(64)`, nullable (SHA-256 of normalized text).
   - Added self-referencing relationship `parent_chunk` and `child_chunks` with `remote_side=[id]` and `passive_deletes=True`.
   - Added database indexes: `idx_chunks_parent_id`, `idx_chunks_chunk_type`, and `idx_chunks_content_hash`.

3. **`alembic/versions/20261024_1012_0e464616411f_add_hierarchical_chunking_and_metadata.py`**
   - Created safe, reversible Alembic migration adding the four new columns and their respective indexes.
   - Applied to live PostgreSQL 16 database without disrupting existing rows or the Phase 1 HNSW index.

4. **`backend/app/services/chunker.py`**
   - Re-architected chunker with `HierarchicalChunk`, `ParentChunk`, `ChildChunk`, and `ChunkMetadata` dataclasses.
   - Implemented `split_hierarchical(text, doc_metadata, doc_type)`:
     - Splits documents by Markdown headers (`#`, `##`, `###`) into discrete sections.
     - Detects and preserves Markdown tables with header/delimiter replication across split row chunks.
     - Preserves paragraph boundaries (`\n\n`) within sections.
     - Bounded child chunk overlap calculation (prevents small-chunk overlap overflow).
     - Strict date format (`YYYY-MM-DD`) and calendar validation using `datetime.strptime`.
     - Exact payment code extraction (`scheme`: `VISA`, `MASTERCARD`, `NACHA`, `AMEX`; `condition_code`: e.g. `10.4`, `R01`, `R08`, `DUP_HOLD`).
     - SHA-256 content hashing for deduplication.
   - Maintained backward-compatible `split_document()` returning flat chunks.

5. **`backend/app/services/ingestion.py`**
   - Added `ingest_hierarchical_document(doc_data, doc_id, session)`:
     - Ingests parent chunks, persists them to obtain database IDs, then generates and links child chunks with `parent_chunk_id`.
     - Populates `chunk_type="parent"` for parent sections and `chunk_type="child"` for retrieval chunks.
   - Updated `ingest_document(..., hierarchical=True)` to route to hierarchical ingestion while keeping flat fallback option.

6. **`backend/app/schemas/knowledge.py`**
   - Added optional metadata fields to `SearchResultItem`: `parent_chunk_id`, `chunk_type`, `section_title`, `parent_content`, `content_hash`, `scheme`, `condition_code`, `effective_date`, `page_number`, `source_document`.
   - Added filter parameters to `KnowledgeSearchRequest`: `scheme`, `condition_code`, `include_parent_context: bool = True`.
   - Added `hierarchical: bool = True` to `KnowledgeIngestRequest`.

7. **`backend/app/api/knowledge.py`**
   - Forwarded `hierarchical=request.hierarchical` to `DocumentIngestionPipeline.ingest_document`.

8. **`backend/app/services/retrieval.py`**
   - Filtered out parent chunks (`document_chunks.chunk_type != 'parent'`) from both lexical and semantic searches so child chunks serve as primary retrieval units.
   - Implemented batch-fetching of parent sections via `parent_chunk_id IN (...)`.
   - Attached deduplicated `parent_content` to search results when `include_parent_context=True`.
   - Added metadata filtering for `scheme` and `condition_code` in both PostgreSQL and SQLite fallback queries.

9. **`backend/app/scripts/seed_data.py`**
   - Added `backfill_hierarchical_knowledge_documents(session, batch_size=5)` to re-ingest knowledge documents into parent-child hierarchy.
   - Updated `seed_knowledge_documents` to populate `chunk_type="standalone"`, `section_title`, and `content_hash`.
   - Added `--hierarchical` CLI option to `seed_data.py`.

10. **`backend/tests/conftest.py`**
    - Configured SQLite connection listener `set_sqlite_pragma` executing `PRAGMA foreign_keys=ON;` to verify foreign key referential integrity in in-memory test environments.

11. **`backend/tests/test_hierarchical_chunking_phase2.py`**
    - Created comprehensive test suite with 20 unit tests covering:
      - Short document handling (no unnecessary split).
      - Long document splitting and paragraph preservation.
      - Overlap behavior and empty document handling.
      - Duplicate chunk detection via SHA-256 `content_hash`.
      - Markdown table preservation and header replication on split rows.
      - Exact numeric, code, and dollar amount preservation.
      - Strict date validation (rejecting leap year errors like `2024-02-30`).
      - Scheme and condition code extraction without hallucination.
      - Database persistence, child-to-parent foreign keys, and `ON DELETE SET NULL` cascade behavior.
      - Retrieval pipeline child filtering, parent context attachment, and parent deduplication.
      - Lexical search fallback and synthetic vector exclusion.

12. **`backend/tests/test_postgres_integration.py`**
    - Added `test_postgres_hierarchical_chunking_and_metadata_indexes` verifying migration columns, parent-child foreign key resolution, and query plans on live PostgreSQL 16.

---

## 4. Schema and Migration Changes

### Migration Summary
- **Migration Script:** `alembic/versions/20261024_1012_0e464616411f_add_hierarchical_chunking_and_metadata.py`
- **Revision ID:** `0e464616411f`
- **Revises:** `1876c4722542` (Phase 1 HNSW index)
- **Status on Live PostgreSQL 16:** **APPLIED AND VERIFIED (`0e464616411f (head)`)**

### DDL Operations Executed
```sql
ALTER TABLE document_chunks ADD COLUMN parent_chunk_id UUID REFERENCES document_chunks(id) ON DELETE SET NULL;
ALTER TABLE document_chunks ADD COLUMN chunk_type VARCHAR(32) DEFAULT 'child';
ALTER TABLE document_chunks ADD COLUMN section_title VARCHAR(255);
ALTER TABLE document_chunks ADD COLUMN content_hash VARCHAR(64);

CREATE INDEX idx_chunks_parent_id ON document_chunks(parent_chunk_id);
CREATE INDEX idx_chunks_chunk_type ON document_chunks(chunk_type);
CREATE INDEX idx_chunks_content_hash ON document_chunks(content_hash);
```

### Safety and Non-Destructive Invariants
1. **Zero Data Loss:** All existing rows in `document_chunks` and `knowledge_documents` were preserved. New columns are nullable with safe defaults (`chunk_type='child'`).
2. **Phase 1 Indexes Preserved:** The HNSW cosine index `idx_document_chunks_embedding_hnsw` and PostgreSQL FTS GIN index `idx_document_chunks_tsv` remained completely intact and valid.
3. **Foreign Key Integrity:** `parent_chunk_id` enforces a foreign key back to `document_chunks(id)`. If a parent section is deleted, child chunks have their `parent_chunk_id` set to `NULL` (`ON DELETE SET NULL`) rather than failing or causing cascading deletions.
4. **Reversible Downgrade:** The migration includes an exact `downgrade()` function dropping the three indexes, dropping the foreign key constraint, and removing the four added columns.

---

## 5. Parent-Child Chunking Design

### Configurable Defaults
- **Parent Chunk Target:** 1,000 tokens (configured via `CHUNK_PARENT_SIZE = 1000`).
- **Parent Chunk Overlap:** 100 tokens (configured via `CHUNK_PARENT_OVERLAP = 100`).
- **Child Chunk Target:** 200 tokens (configured via `CHUNK_CHILD_SIZE = 200`).
- **Child Chunk Overlap:** 30 tokens (configured via `CHUNK_CHILD_OVERLAP = 30`).

### Ingestion & Splitting Lifecycle
```
[ Raw Knowledge Document (Markdown / Text) ]
                     │
                     ▼
  1. Header Analysis & Section Extraction
     - Scans for '#', '##', '###' markers
     - Identifies section title and boundaries
                     │
                     ▼
  2. Parent Section Generation (~1,000 tokens)
     - Preserves section title prefix ('## Header')
     - Retains full narrative context
     - Persisted as chunk_type='parent'
                     │
                     ▼
  3. Child Chunk Generation (~200 tokens)
     - Paragraph-aware splitting ('\n\n')
     - Table boundary isolation
     - Bounded overlap (min(overlap, target // 4))
     - Persisted with parent_chunk_id -> Parent.id
     - Tagged with chunk_type='child'
```

### Edge Case Handling
1. **Short Documents:** Documents under the parent target size (< 1,000 tokens) are treated as a single parent section yielding a single child chunk, preventing arbitrary fragmenting of short policies.
2. **Long Documents:** Long multi-page documents are split into clean sections with overlap, ensuring no text is silently dropped.
3. **Empty / Whitespace Documents:** Produces an empty chunk list without generating empty records or database errors.
4. **Duplicate Content:** Computes SHA-256 hash of normalized content (`content_hash`). Identical chunks can be identified and skipped during backfills.

---

## 6. Metadata Extraction and Validation

### Supported Metadata Schema
The pipeline extracts structured metadata directly into chunk records and the JSONB `metadata` dictionary:

| Field | Source / Rule | Validation / Constraint | Example Value |
|---|---|---|---|
| `document_id` | Foreign key to `knowledge_documents.id` | Required UUID | `221ffb76-4004-442c-88aa-85d6bbe1f0e9` |
| `parent_chunk_id` | Foreign key to `document_chunks.id` | Nullable UUID | `daef57e1-e3f1-448c-99e5-fb39c4ae0507` |
| `chunk_type` | Chunk classification | `"parent"`, `"child"`, `"standalone"` | `"child"` |
| `section_title` | Markdown heading or section name | String (max 255 chars) | `"Reason Code 10.4: Other Fraud"` |
| `scheme` | Detected card/payment network | Validated against known schemes: `VISA`, `MASTERCARD`, `NACHA`, `AMEX`, `INTERNAL` | `"VISA"` |
| `condition_code` | Technical dispute/return code | Regex pattern matching (`10.4`, `R01`, `R08`, `DUP_HOLD`) | `"10.4"` |
| `effective_date` | Date string in document | Strict ISO-8601 `YYYY-MM-DD` and real calendar date check (`datetime.strptime`) | `"2024-04-15"` |
| `source_document` | Original document title/filename | Preserved from document metadata | `"Visa Core Rules - 10.4"` |
| `page_number` | Page numbering if present | Nullable positive integer | `1` |
| `chunk_index` | Zero-indexed chunk sequence | Non-negative integer | `0` |
| `content_hash` | SHA-256 of normalized text | 64-character hexadecimal string | `a79f...3e21` |
| `embedding_model` | Model used for vectorization | String identifier or NULL | `"text-embedding-3-small"` |
| `created_at` | Ingestion timestamp | UTC datetime | `2026-10-24 10:14:12` |

### Anti-Hallucination Policy
- Metadata fields (`scheme`, `condition_code`, `effective_date`) are only populated if explicitly present in the document text or trusted source metadata.
- Dates failing strict calendar validation (e.g. `2024-02-30` or `2023-13-01`) are rejected and set to `None`.
- Missing schemes or condition codes are left as `None` rather than guessed.

---

## 7. Table Preservation Behavior and Limitations

### Preservation Architecture
Documents containing structured Markdown tables (e.g., dispute condition matrices, fee schedules, SLA turnaround tables) are handled using a dedicated table-aware splitting parser (`_split_table_into_chunks`):
1. **Header & Separator Attachment:** The table header row (`| Code | Description | SLA |`) and markdown separator row (`|---|---|---|`) are retained.
2. **Row Preservation:** Related rows are kept together up to the configured chunk limit.
3. **Oversized Table Slicing:** When a table has many rows exceeding the child chunk limit (200 tokens), the table is sliced along row boundaries, and the header and separator rows are prepended to every slice.
4. **Exact Value Retention:** Technical codes (e.g., `10.4`, `R01`, `R08`), monetary figures (`$149.00`, `$2,500.00`), and identifiers (`ARN 74512349012348572019283`) are preserved without delimiter distortion or line wrapping.

### Verified Table Test Example
Input table with 3 distinct condition rows split with a 40-token limit:
- **Slice 1:** Header + Row 1 (`10.4` Card-absent fraud).
- **Slice 2:** Header + Row 2 (`10.5` Card-present fraud).
- **Slice 3:** Header + Row 3 (`10.6` Chip liability shift).
Both slices retain exact column headers, allowing the retrieval model to interpret each row in its semantic context.

### Documented Parser Limitation
The current parser specifically targets **Markdown-formatted tables** (delimited with `|`). Raw PDFs with visual coordinate tables, ASCII-bordered box tables, or unformatted multi-column OCR outputs require an OCR layout analysis or multi-modal visual parser (such as LayoutLM or Gemini Vision) to convert visual tables to Markdown prior to ingestion.

---

## 8. Retrieval Integration

### Child-First Retrieval Strategy
In Phase 2, the retrieval pipeline was upgraded to use child chunks as the primary retrieval targets:
1. **Exclusion of Parent Chunks:** Both `lexical_search` (PostgreSQL tsvector full-text search) and `semantic_search` (pgvector cosine distance `<=>`) apply the filter:
   ```sql
   WHERE document_chunks.chunk_type != 'parent' OR document_chunks.chunk_type IS NULL
   ```
   This ensures that small, high-density child chunks receive the highest lexical and semantic similarity scores, rather than diluted 1,000-token parent chunks.
2. **Parent Context Attachment:**
   - Once the top-$K$ child chunks are retrieved and ranked, the service gathers distinct `parent_chunk_id` values.
   - A single batch query fetches the parent chunks:
     ```sql
     SELECT * FROM document_chunks WHERE id IN (:parent_ids)
     ```
   - The full parent text is attached to the result item as `parent_content`, providing the calling application or LLM agent with surrounding context.
3. **Parent Context Deduplication:**
   - When multiple retrieved child chunks originate from the same parent section, they reference the same parent chunk. The retrieval service attaches the parent text without querying the database redundantly.
4. **Metadata Filtering:**
   - Callers can filter search results by `scheme` (e.g. `scheme="VISA"`) or `condition_code` (e.g. `condition_code="10.4"`).
5. **Synthetic Placeholder Exclusion:**
   - Maintained Phase 1 guarantee: Chunks with `embedding_model="synthetic_placeholder"` are excluded from vector similarity scoring.
6. **Lexical Fallback:**
   - If the embedding provider is offline, unconfigured, or lacks an API key, the retrieval pipeline seamlessly executes PostgreSQL full-text search with `plainto_tsquery` and `to_tsquery` ranking via `ts_rank_cd`.

---

## 9. Tests Run and Exact Pass/Fail Counts

### Summary of Test Execution
- **Total Backend Tests:** **160 passed in 79.03s** (0 failures, 0 errors).
- **Phase 2 Test Suite (`test_hierarchical_chunking_phase2.py`):** **20/20 passed**.
- **PostgreSQL 16 Integration Suite (`test_postgres_integration.py`):** **7/7 passed**.
- **Phase 1 RAG Regression Suite (`test_rag_production_phase1.py`):** **10/10 passed**.
- **Frontend Production Build (`npm run build`):** **10/10 routes compiled successfully (0 errors)**.

### Detailed Breakdown of Phase 2 Tests

| Test Function | Category | Verified Requirement | Status |
|---|---|---|---|
| `test_chunker_short_document_no_unnecessary_split` | Chunking | Short document (< parent size) produces 1 parent and 1 child | **PASS** |
| `test_chunker_long_document_splits_cleanly` | Chunking | Long document divides into multiple parents and children without dropping content | **PASS** |
| `test_chunker_paragraph_boundaries_preserved` | Chunking | Paragraphs separated by `\n\n` are preserved in child chunks | **PASS** |
| `test_chunker_overlap_behavior` | Chunking | Overlap between adjacent child chunks is correctly populated | **PASS** |
| `test_chunker_empty_and_whitespace_documents` | Chunking | Empty documents yield 0 chunks without throwing errors | **PASS** |
| `test_chunker_duplicate_content_hash` | Chunking | Identical texts produce identical SHA-256 hashes | **PASS** |
| `test_chunker_table_preservation_with_headers` | Structured Content | Table headers are replicated across split row chunks | **PASS** |
| `test_chunker_table_exact_numeric_and_code_preservation` | Structured Content | Codes (`10.4`, `R01`), amounts (`$149.00`), and ARNs are preserved exactly | **PASS** |
| `test_metadata_strict_date_validation` | Metadata | Valid dates parsed; invalid dates (`2024-02-30`) rejected | **PASS** |
| `test_metadata_extraction_without_fabrication` | Metadata | Schemes and condition codes extracted; missing values set to `None` | **PASS** |
| `test_hierarchical_ingestion_persistence_and_relationships` | Hierarchy | Ingestion persists parents and children; children link to parent IDs | **PASS** |
| `test_referential_integrity_on_delete_parent` | Hierarchy | Deleting parent sets `parent_chunk_id=NULL` without deleting child | **PASS** |
| `test_retrieval_child_chunks_with_parent_context` | Retrieval | Child chunks retrieved; `parent_content` attached | **PASS** |
| `test_retrieval_parent_context_deduplication` | Retrieval | Multiple child chunks sharing a parent reference the same parent cleanly | **PASS** |
| `test_retrieval_excludes_synthetic_placeholders` | Retrieval | Chunks tagged `synthetic_placeholder` excluded from vector search | **PASS** |
| `test_retrieval_lexical_fallback_when_embedding_offline` | Retrieval | Lexical FTS returns results when embedding provider is offline | **PASS** |
| `test_retrieval_metadata_filters_scheme_and_condition` | Retrieval | Filtering by scheme and condition code restricts search results | **PASS** |
| `test_reingestion_backfill_idempotent` | Re-ingestion | Ingesting same document replaces/updates without orphan duplication | **PASS** |
| `test_chunk_sizes_configurable_via_settings` | Configuration | Config parameters (`CHUNK_PARENT_SIZE`, etc.) override defaults | **PASS** |
| `test_oversized_table_split_repeated_headers` | Structured Content | Multi-row table exceeding child size splits with repeated headers | **PASS** |
| `test_postgres_hierarchical_chunking_and_metadata_indexes` | PostgreSQL Integration | Columns and indexes active in live PostgreSQL 16 catalog | **PASS** |

---

## 10. Performance and Quality Metrics

The live database backfill and retrieval performance were measured against the authoritative test corpus in PostgreSQL 16 (`payguard_postgres`):

### Ingestion and Backfill Metrics
- **Source Documents Processed:** 5 authoritative documents:
  1. Visa Core Rules - Condition 10.4 Dispute Guidelines
  2. NACHA Operating Rules - Return Reason Code R01/R08
  3. Merchant Billing - Duplicate Charge Investigation SOP
  4. Refund SLA and Acquirer Reference Number (ARN) Tracking
  5. Operations Triage SOP - Evidence Requirements
- **Parent Chunks Created:** 10 sections.
- **Child Chunks Created:** 10 chunks.
- **Average Child Chunk Size:** 82.0 tokens.
- **Maximum Child Chunk Size:** 99.0 tokens (comfortably within the 200-token target limit).
- **Chunks with Missing Required Relationships:** **0** (100% of child chunks reference a valid parent chunk).
- **Duplicate Chunks Detected:** **0**.

### Live PostgreSQL 16 Retrieval Latency
Measured across representative benchmark queries on PostgreSQL 16 with parent context expansion enabled:

| Benchmark Query | Chunks Retrieved | Elapsed Latency |
|---|---|---|
| `Visa return reason code 10.4 fraud` | 3 child chunks + 2 parents | 28.74 ms |
| `ACH unauthorized debit R01` | 3 child chunks + 2 parents | 22.25 ms |
| `Refund SLA ARN 74512349012348572019283` | 3 child chunks + 2 parents | 18.97 ms |
| `Merchant billing duplicate hold $149.00` | 5 child chunks + 3 parents | 17.22 ms |
| `Operations SOP escalation policy` | 2 child chunks + 2 parents | 20.69 ms |
| **Average Warm Retrieval Latency** | — | **21.58 ms** (Min: 17.22 ms, Max: 28.74 ms) |

*Note: Initial cold engine connection pool creation on Windows required ~498ms on the first query; subsequent warm queries averaged 21.58ms.*

---

## 11. Known Limitations

1. **Approximate Tokenizer:** Token counting uses a consistent 4-character / whitespace-word ratio approximation. While fast, deterministic, and dependency-free, exact token counts can differ slightly (+/- 5%) from proprietary BPE tokenizers (like `cl100k_base`).
2. **Markdown Table Parsing Scope:** The table-aware splitting parser specifically targets Markdown tables (`| ... |`). Documents with tables embedded as raw unformatted text or PDF image coordinates require an OCR pre-processing step before ingestion.
3. **External Real Embeddings:** Because `OPENAI_API_KEY` is not present in the local staging environment, live vector embeddings are not generated against the external OpenAI network. Retrieval operates via PostgreSQL full-text search fallback and mocked embedding providers during unit testing.

---

## 12. Manual Steps Required

- **Database Migrations:** None. Migration `0e464616411f` has already been applied to the live PostgreSQL staging database.
- **Data Backfill:** None. `seed_data.py --hierarchical` has already been executed on the live staging database.
- **Configuration:** Optional: When deploying to production with live OpenAI embeddings, configure `OPENAI_API_KEY` in `.env` and run `python -m backend.app.scripts.seed_data --reembed-live`.

---

## 13. Confirmation: Zero Paid API Calls

It is hereby confirmed that:
- **Zero paid API calls were made** during Phase 2 development, testing, migration, or backfill.
- No `OPENAI_API_KEY` was requested or exposed.
- All 160 unit and integration tests run deterministically using local computation, PostgreSQL full-text search, and mock embedding providers.

---

## 14. Recommended Next Phase

### Phase 3: Context-Aware Re-ranking and Local Cross-Encoder Evaluation
With hierarchical chunks, table preservation, and parent context attachment in place, the RAG engine has high-quality retrieval units. Recommended next steps for Phase 3:
1. **Local Cross-Encoder / Re-ranker:** Introduce an open-weights, local cross-encoder (e.g. `bge-reranker-base` or `ms-marco-MiniLM-L-6-v2`) running locally via ONNX Runtime to score retrieved child chunks against the user query before returning them to the agent.
2. **Score Calibration & Dynamic Thresholding:** Implement dynamic cutoff thresholds to discard low-confidence retrieval matches before prompt assembly.
3. **Agent Context Window Assembly:** Format the retrieved child chunks and attached parent section headers into a clean, markdown-delimited prompt envelope for downstream payment triage agents.
