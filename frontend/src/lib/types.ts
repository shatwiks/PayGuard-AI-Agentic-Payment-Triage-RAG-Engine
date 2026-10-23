/**
 * PayGuard AI TypeScript Types & Schemas
 * Directly aligned with FastAPI Pydantic Models
 */

export type UserRole = "support_agent" | "compliance_analyst" | "admin";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  user_role: UserRole;
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy";
  database: string;
  vector_store: string;
  version: string;
  environment: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export type PaymentStatus =
  | "authorized"
  | "captured"
  | "pending"
  | "failed"
  | "reversed"
  | "refunded"
  | "disputed";

export interface PaymentSummary {
  id: string;
  payment_reference: string;
  customer_id: string;
  merchant_id: string;
  amount: number | string;
  currency: string;
  payment_method: string;
  status: PaymentStatus;
  gateway_name: string;
  created_at: string;
}

export interface PaymentEvent {
  id: string;
  payment_id: string;
  event_type: string;
  from_status: string | null;
  to_status: string;
  raw_payload: Record<string, any>;
  occurred_at: string;
  created_at: string;
}

export interface PaymentDetail extends PaymentSummary {
  gateway_transaction_id: string | null;
  failure_code: string | null;
  failure_message: string | null;
  metadata: Record<string, any>;
  authorized_at: string | null;
  captured_at: string | null;
  updated_at: string;
  events: PaymentEvent[];
}

export type CaseStatus = "open" | "in_progress" | "triaged" | "escalated" | "closed";
export type PriorityLevel = "low" | "medium" | "high" | "urgent";

export interface PolicyCitation {
  document_title: string;
  section_header: string;
  excerpt: string;
  confidence_score: number | null;
  source_id: string | null;
  source_url: string | null;
  document_id: string | null;
  chunk_id: string | null;
  is_synthetic_demonstration: boolean;
}

export interface InvestigationResult {
  id: string;
  case_id: string;
  issue_category: string;
  confidence_score: number;
  investigation_summary: string;
  recommended_action: string;
  recommended_action_details: string;
  policy_citations: PolicyCitation[];
  missing_or_conflicting_info: string[];
  human_review_required: boolean;
  human_review_reason: string | null;
  execution_time_ms: number;
  llm_model_name: string;
  retrieval_mode: string;
  generation_mode: string;
  evidence_package: Record<string, any> | null;
  created_at: string;
}

export interface InvestigationCase {
  id: string;
  case_number: string;
  customer_query: string;
  sanitized_query: string;
  status: CaseStatus;
  priority: PriorityLevel;
  payment_id: string | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
  payment: PaymentSummary | null;
  result: InvestigationResult | null;
}

export interface InvestigationCreateRequest {
  customer_query: string;
  payment_reference?: string;
  payment_id?: string;
  priority?: PriorityLevel;
}

export interface InvestigationMetrics {
  total_cases: number;
  open_cases: number;
  in_progress_cases: number;
  triaged_cases: number;
  escalated_cases: number;
  closed_cases: number;
  by_category: Record<string, number>;
}

export interface RankingDetails {
  lexical_rank?: number | null;
  lexical_score?: number | null;
  semantic_rank?: number | null;
  semantic_distance?: number | null;
  semantic_similarity?: number | null;
  fusion_score: number;
  signals_used: string[];
}

export interface SearchResultItem {
  chunk_id: string;
  document_id: string;
  title: string;
  source_id: string | null;
  source_url: string | null;
  doc_type: string;
  chunk_index: number;
  section_header: string;
  content: string;
  token_count: number;
  embedding_model: string | null;
  retrieval_mode: string | null;
  ranking: RankingDetails;
}

export interface KnowledgeSearchResponse {
  query: string;
  retrieval_mode: string;
  total_candidates: number;
  results_count: number;
  results: SearchResultItem[];
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    field?: string | null;
  };
  timestamp: string;
}
