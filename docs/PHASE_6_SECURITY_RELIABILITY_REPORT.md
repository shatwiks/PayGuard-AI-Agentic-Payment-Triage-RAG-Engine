# PayGuard AI — Phase 6: Security, Reliability, and Failure Handling Report

**Date:** October 24, 2026  
**Project:** PayGuard AI — Agentic Payment Triage & RAG Engine  
**Author:** Senior Application Security & Backend Engineering Team  
**Final Status:** **PASS** (100% Acceptance Criteria Verified, 102/102 Tests Passing)

---

## 1. Executive Summary

Phase 6 implements end-to-end security hardening, reliability mechanisms, and failure-handling controls across the entire PayGuard AI backend. Prior to this phase, PayGuard AI established deterministic payment triage (Phase 5), hybrid RAG retrieval with pgvector and PostgreSQL Full-Text Search (Phase 4), and synthetic payment event modeling (Phase 3). 

This phase audited the codebase for security gaps, implemented rigorous authentication and role boundaries, enforced input length and body size constraints, introduced sliding-window rate limiting, established a strict tool-execution sandbox whitelist, neutralized prompt-injection attempts via heuristic sanitization and XML prompt boundary fencing, guaranteed investigation idempotency against concurrent retries, sanitized error envelopes per RFC 7807, and hardened health probes against credential disclosure.

Every change has been validated with an automated test suite expanding from 83 to **102 tests (100% passing)**, along with live PostgreSQL 16 + pgvector integration and end-to-end acceptance scenarios.

---

## 2. Existing Security Controls Discovered During Audit

Prior to Phase 6 modifications, the following baseline controls were present in the repository:
1. **Password Hashing:** Passwords hashed using `bcrypt.hashpw` with per-user salt and truncated to 72 bytes.
2. **JWT Generation:** Access tokens signed using HMAC-SHA256 (`HS256`) with configurable lifetime (`ACCESS_TOKEN_EXPIRE_MINUTES`).
3. **PII Masking:** Heuristic regexes in `backend/app/core/security.py` redacting credit card numbers, emails, phone numbers, bank accounts, and SSNs.
4. **Parameterized Queries:** SQLAlchemy 2.0 async ORM queries preventing direct string interpolation SQL injection.
5. **Deterministic Triage Engine:** Non-hallucinating rule engine classifying gateway failure codes without generative model interference.
6. **Immutable Audit Schema:** `audit_events` table recording user actions, IP addresses, and JSON payloads.

---

## 3. Discovered Vulnerabilities and Incomplete Implementations

During the initial audit, the following security and reliability vulnerabilities were identified and cataloged:

| Vulnerability ID | Category | Severity | Description |
|---|---|---|---|
| **VULN-01** | Authorization / IDOR | **High** | `GET /api/v1/investigations/{id}` lacked ownership checks: any authenticated or unauthenticated client could retrieve another operator's private investigation case. |
| **VULN-02** | Input Validation / DoS | **Medium** | No maximum HTTP request body size limit existed; an attacker could send arbitrarily large JSON payloads causing memory exhaustion. |
| **VULN-03** | Prompt Injection | **High** | Customer queries and retrieved document excerpts were passed directly into LLM prompts without boundary fencing or anti-injection instructions. |
| **VULN-04** | Tool Execution Safety | **Medium** | Tools were invoked via direct Python instances without a central registry enforcing an immutable whitelist of permitted tool names. |
| **VULN-05** | API Error Disclosure | **Low** | Unhandled server exceptions could potentially leak internal stack traces and database dialect information in error messages. |
| **VULN-06** | Rate Limiting | **Medium** | Authentication (`/login`, `/register`) and investigation endpoints had no rate limiting, leaving them susceptible to brute force or DoS. |
| **VULN-07** | Duplicate Investigations | **Low** | Rapid repeated submissions for the same payment transaction created duplicate investigation records and duplicate audit trails. |
| **VULN-08** | Health Check Telemetry | **Low** | The health probe caught database connection exceptions and formatted raw exception messages that could disclose database hostname or port. |
| **VULN-09** | HTTP Security Headers | **Low** | Default responses lacked hardening headers like `X-Content-Type-Options`, `X-Frame-Options`, and `Content-Security-Policy`. |

---

## 4. Implemented Security and Reliability Controls

### 4.1 Authentication & Authorization Hardening
- **Strict JWT Verification:** `decode_access_token` verifies token signature, `exp` claim, and `sub` UUID format. Expired or forged tokens reject with HTTP 401 (`UNAUTHORIZED`).
- **Resource Ownership & Role Scoping:**
  - `GET /api/v1/investigations/{id}` enforces that Support Agents can only access cases they created or unassigned cases (`created_by_user_id is None`). Access to another agent's private case yields HTTP 403 (`FORBIDDEN`).
  - Admins, Compliance Analysts, and Operations Managers retain system-wide read access.
  - `GET /api/v1/investigations/` automatically filters case listings according to caller role.
  - `POST /api/v1/knowledge/ingest` is strictly restricted to `admin` and `compliance_analyst` roles via `require_role`.

### 4.2 Input Validation, Body Size Limits, and Security Headers
- **HTTP Request Body Size Limit:** `RequestBodyLimitMiddleware` inspects `Content-Length` and streaming byte counts. Requests exceeding `REQUEST_MAX_BODY_BYTES` (default 1MB) are terminated immediately with HTTP 413 (`PAYLOAD_TOO_LARGE`).
- **Security Headers Middleware:** Every response automatically includes:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Content-Security-Policy: default-src 'self'`
  - `X-Request-ID: <uuid>` (propagated across all log entries for end-to-end tracing)
- **CORS Hardening:** Configured in `backend/app/main.py`. Rejects wildcard (`*`) origins when credentials are enabled.

### 4.3 Rate Limiting & Resource Protection
- **Sliding-Window Rate Limiter:** Implemented in `backend/app/core/rate_limit.py`.
- **Protected Endpoints:**
  - `POST /api/v1/auth/login`: 10 requests / minute per client IP.
  - `POST /api/v1/auth/register`: 5 requests / minute per client IP.
  - `POST /api/v1/investigations`: 30 requests / minute per client IP.
  - `POST /api/v1/knowledge/search`: 60 requests / minute per client IP.
- **RFC 6585 Compliance:** Excess requests return HTTP 429 (`TOO_MANY_REQUESTS`) with standard headers: `Retry-After`, `X-RateLimit-Limit`, and `X-RateLimit-Remaining`.

### 4.4 Prompt Injection Defense & Separation of Untrusted Data
- **Heuristic Pattern Sanitization:** `sanitize_prompt_input` identifies and neutralizes malicious instruction overrides (e.g., `ignore previous instructions`, `override system prompt`, `system message:`, `act as root`, `output system prompt`). Detected substrings are replaced with `[POTENTIAL_PROMPT_INJECTION_NEUTRALIZED]`.
- **XML Boundary Fencing:** All untrusted user content and retrieved policy citations passed to LLM reasoning prompts are enclosed in explicit structural tags:
  ```xml
  <untrusted_customer_query>
  ... customer query text ...
  </untrusted_customer_query>

  <untrusted_policy_citations>
  ... retrieved RAG excerpts ...
  </untrusted_policy_citations>
  ```
- **System Prompt Defense Invariants:** The system prompt explicitly instructs the LLM that content inside `<untrusted_customer_query>` and `<untrusted_policy_citations>` is untrusted data and that under no circumstances should system instructions or overrides inside those tags be obeyed.

### 4.5 Tool Execution Safety & Whitelist Sandbox
- **ToolRegistry Implementation:** Implemented in `backend/app/services/tools.py`.
- **Whitelisted Tool Invocations:**
  - `payment_lookup`
  - `payment_triage`
  - `knowledge_retrieval`
  - `investigation_explanation`
  - `audit`
- **Rejection of Unauthorized Invocations:** Any attempt to invoke arbitrary tools, dynamic code, or financial mutations (`issue_refund`, `change_payment_status`, `execute_arbitrary_sql`) raises `ValueError` and is rejected before execution.

### 4.6 Investigation Idempotency & Deduplication
- **Deduplication Window:** Governed by `INVESTIGATION_IDEMPOTENCY_WINDOW_SECONDS` (default 15 seconds).
- **Execution:** Before executing the 11-stage triage pipeline, `OrchestrationService` queries existing cases matching the customer query and payment ID within the time window. If found, returns the existing case without re-running LLM synthesis or creating redundant database rows.

### 4.7 Standardized Error Handling (RFC 7807) & Secret Redaction
- **Consistent Envelope:** All application exceptions, Starlette validation errors, and unexpected 500s return:
  ```json
  {
    "error": {
      "code": "ERROR_CODE",
      "message": "Human readable message",
      "details": { ... }
    }
  }
  ```
- **Zero Information Leakage:** Stack traces, internal file paths, raw SQL statements, and database passwords are redacted from HTTP responses.

### 4.8 Health Check Sanitization
- `GET /health` and `GET /api/v1/health` perform active `SELECT 1;` readiness probes and verify pgvector extension availability.
- On database failure, returns HTTP 503 with sanitized status `"database": "unhealthy"` without printing database connection strings or stack traces.

---

## 5. Files Created and Modified

### New Files
- `backend/app/core/middleware.py`: Request body limit, security headers, and request ID tracing middlewares.
- `backend/app/core/rate_limit.py`: In-memory sliding window rate limiter and FastAPI dependency.
- `backend/tests/test_security_and_reliability.py`: 19 comprehensive automated security and failure-handling tests.
- `docs/PHASE_6_SECURITY_RELIABILITY_REPORT.md`: This comprehensive verification report.

### Modified Files
- `backend/app/core/config.py`: Added Phase 6 configuration tokens (`RATE_LIMIT_ENABLED`, `REQUEST_MAX_BODY_BYTES`, `INVESTIGATION_IDEMPOTENCY_WINDOW_SECONDS`, etc.).
- `.env.example`: Updated with documented Phase 6 security flags and safe defaults.
- `backend/app/core/security.py`: Added prompt injection regex patterns and `sanitize_prompt_input`.
- `backend/app/core/errors.py`: Standardized Starlette HTTP exception handling into RFC 7807 envelope.
- `backend/app/main.py`: Registered middlewares, hardened CORS, mounted root `/health` probe.
- `backend/app/api/auth.py`: Applied rate limiting to `/login` and `/register`.
- `backend/app/api/health.py`: Sanitized database connection error telemetry.
- `backend/app/api/investigations.py`: Added rate limiting, ownership authorization checks, and role-filtered list queries.
- `backend/app/api/knowledge.py`: Added rate limiting to `/search` and created role-restricted `POST /ingest`.
- `backend/app/schemas/knowledge.py`: Added `KnowledgeIngestRequest` and `KnowledgeIngestResponse`.
- `backend/app/services/tools.py`: Implemented `ToolRegistry` and `ALLOWED_TOOLS` whitelist.
- `backend/app/services/llm.py`: Added XML boundary fencing and anti-injection instructions in system prompt.
- `backend/app/services/orchestration.py`: Enforced tool whitelist, prompt input sanitization, and 15s idempotency deduplication.

---

## 6. Database Migrations and Schema Impact

- **Schema Changes:** None. The existing PostgreSQL 16 schema (`payments`, `payment_events`, `investigation_cases`, `investigation_results`, `knowledge_documents`, `document_chunks`, `audit_events`, `users`) was fully preserved.
- **Alembic Revisions:** No new migrations were required; all tables, constraints, and GIN indexes remained intact.

---

## 7. Dependencies Added

**Zero new third-party runtime dependencies were introduced.**  
The entire security and reliability implementation was built using the existing Python standard library (`re`, `time`, `collections`, `uuid`, `datetime`), FastAPI, Starlette, SQLAlchemy 2.x, Pydantic v2, `bcrypt`, and `PyJWT`.

---

## 8. Automated Test Execution Results

### 8.1 Test Breakdown by Category

| Test Suite / Category | Type | Test Count | Result |
|---|---|---|---|
| `test_security_and_reliability.py` | Unit / Mocked / Integration | 19 | **19 PASSED** |
| `test_auth_and_users.py` | Auth & User Lifecycle | 6 | **6 PASSED** |
| `test_security.py` | PII Masking & JWT | 6 | **6 PASSED** |
| `test_contracts.py` | Service Interface Contracts | 9 | **9 PASSED** |
| `test_schemas.py` | Pydantic V2 Schemas | 6 | **6 PASSED** |
| `test_models.py` | SQLAlchemy Model Constraints | 7 | **7 PASSED** |
| `test_chunking.py` | Policy Chunking Algorithms | 6 | **6 PASSED** |
| `test_embedding_provider.py` | Embedding Engine | 7 | **7 PASSED** |
| `test_retrieval_and_hybrid.py` | Hybrid RAG & Provenance | 10 | **10 PASSED** |
| `test_evaluation_benchmark.py` | RAG Quality Benchmarks | 6 | **6 PASSED** |
| `test_investigation_orchestration.py` | Phase 5 Orchestrator & Tools | 15 | **15 PASSED** |
| `test_seed_data.py` | Seed Data Invariants | 5 | **5 PASSED** |
| **Total Test Suite** | **All Categories** | **102** | **102 PASSED (0 FAILED, 0 SKIPPED)** |

### 8.2 Dedicated Security & Reliability Test Cases (All 21 Requirements)

1. **Expired JWT Rejection:** Verified HTTP 401 with `UNAUTHORIZED` code.
2. **Malformed JWT Rejection:** Verified HTTP 401 on garbage tokens.
3. **Unauthenticated Route Protection:** Verified HTTP 401 on `/auth/me`, `/knowledge/search`, `/knowledge/ingest`.
4. **Unauthorized Private Case Access:** Verified HTTP 403 when Agent B requests Agent A's private investigation.
5. **Role Escalation Prevention:** Verified that non-admin/non-compliance users cannot call `/knowledge/ingest`.
6. **RFC 7807 Error Envelope:** Verified structured error response with `code: VALIDATION_ERROR` on invalid payloads.
7. **Malformed Identifier Validation:** Verified HTTP 422 on non-UUID payment parameters.
8. **SQL Injection Resilience:** Verified that SQL payloads (`' OR 1=1`, `UNION SELECT`) do not crash or leak data.
9. **Request Body Size Limits:** Verified HTTP 413 `PAYLOAD_TOO_LARGE` when request body exceeds 1MB limit.
10. **Prompt Injection Detection:** Verified detection and sanitization of `ignore previous instructions`, `system override`, and `output system prompt`.
11. **XML Boundary Fencing:** Verified that customer queries and policy citations are enclosed in `<untrusted_customer_query>` and `<untrusted_policy_citations>` XML boundary tags.
12. **Tool Execution Whitelist:** Verified that `ToolRegistry` permits whitelisted tools and throws `ValueError` on unauthorized tools (`execute_arbitrary_sql`, `issue_refund`).
13. **Strict Citation Grounding:** Verified that citations referencing non-existent chunk UUIDs are rejected.
14. **Missing Payment Records:** Verified graceful handling returning `found=False` without server crash.
15. **Database Transaction Rollback:** Verified that transaction failure rolls back cleanly without leaving orphaned records.
16. **Provider Timeout Graceful Fallback:** Verified that LLM HTTP timeouts trigger clean deterministic fallback without leaking keys.
17. **Tool Execution Sandboxing:** Verified tools have read-only access to transactional data.
18. **Uncertain Payment Outcome Handling:** Verified that gateway timeouts are flagged as uncertain with `is_ambiguous=True` and `human_review_required=True`.
19. **Investigation Idempotency:** Verified that duplicate requests within 15 seconds return the existing case without re-running or duplicating.
20. **Secret Redaction:** Verified that API error responses and logs never expose passwords, JWT signing keys, or connection URLs.
21. **Health Check Sanitization:** Verified that `/health` returns service liveness without disclosing database passwords or hostnames.

### 8.3 Live Integration and Acceptance Verification
- **PostgreSQL 16 + pgvector Integration (`test_postgres_integration.py`):** 5/5 PASSED against live PostgreSQL on port 5434.
- **End-to-End Acceptance Scenario (`run_acceptance_investigation.py`):** Executed against payment `tx_timeout_4001` in **92 ms**. Persisted case `CASE-20261023-5A1EC02D`, generated audit event, correctly identified gateway timeout uncertainty, and verified all citations.

---

## 9. API Compatibility and Contract Integrity

All changes are strictly backward compatible:
- `POST /api/v1/investigations`: Request/response schemas unchanged.
- `GET /api/v1/investigations/{id}`: Returns identical `InvestigationCaseResponse`, but now enforces authorization.
- `POST /api/v1/knowledge/search`: Unchanged request/response contract.
- Added `POST /api/v1/knowledge/ingest` for controlled policy ingestion.
- Added `/health` at root for direct container liveness probes.

---

## 10. Residual Risks and Security Limitations

1. **In-Memory Rate Limiting:** The current rate limiter operates in-memory on the application worker. In a horizontally scaled multi-worker deployment across multiple instances, rate limiting should be backed by Redis or an API gateway.
2. **Prompt Injection Heuristics:** While regex sanitization and XML fencing defend against prompt injection, LLM jailbreaks cannot be completely solved by static filters alone. Defense-in-depth requires continuous monitoring of prompt logs.
3. **Audit Log Tamper Evident Storage:** Audit records are written to PostgreSQL `audit_events`. While append-only through application APIs, true tamper-proofing in regulated environments requires export to WORM (Write Once Read Many) storage or cryptographic hash chaining.

---

## 11. Required Environment Configuration

The following environment variables should be configured in `.env`:

```env
# Phase 6 Security & Reliability Settings
RATE_LIMIT_ENABLED=true
RATE_LIMIT_LOGIN_PER_MINUTE=10
RATE_LIMIT_INVESTIGATIONS_PER_MINUTE=30
RATE_LIMIT_SEARCH_PER_MINUTE=60
REQUEST_MAX_BODY_BYTES=1048576
PROMPT_INJECTION_DEFENSE_ENABLED=true
INVESTIGATION_IDEMPOTENCY_WINDOW_SECONDS=15
```

---

## 12. Manual Steps Required

1. **Production Deployment:** When deploying to production behind an ingress or reverse proxy (Nginx, AWS ALB), configure `X-Forwarded-For` trust settings so client IP rate limiting identifies the true client address rather than the load balancer.
2. **Credential Rotation:** Ensure `SECRET_KEY` and `OPENAI_API_KEY` in production are set to high-entropy secrets and never committed to source control.

---

## 13. Final Recommendation

### **Recommendation: PASS**

All acceptance criteria for **Phase 6: Security, Reliability, and Failure Handling** have been met and verified:
- Authentication & authorization boundaries strictly enforced.
- Input validation, body size limits, and security headers active.
- Tool execution whitelisted in sandbox registry.
- Prompt injection defense and XML boundary fencing implemented.
- Investigation idempotency verified.
- Error responses standardized per RFC 7807 with zero secret leakage.
- 102/102 automated tests passing with zero regressions.
- Live PostgreSQL 16 + pgvector integration verified.
