/**
 * PayGuard AI Centralized API Client
 * Robust, production-grade client interacting directly with FastAPI endpoints.
 * Handles JWT authentication, RFC 7807 error envelopes, rate limits (429), timeouts, and network errors.
 */

import {
  ApiErrorEnvelope,
  DocumentAskResponse,
  DocumentUploadResponse,
  HealthResponse,
  InvestigationCase,
  InvestigationCreateRequest,
  InvestigationMetrics,
  KnowledgeSearchResponse,
  PaginatedResponse,
  PaymentDetail,
  PaymentSummary,
  TokenResponse,
  User,
  UserDocumentDetail,
  UserDocumentSummary,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  public code: string;
  public status: number;
  public field?: string | null;
  public retryAfter?: number | null;

  constructor(
    message: string,
    status: number,
    code: string = "API_ERROR",
    field?: string | null,
    retryAfter?: number | null
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.field = field;
    this.retryAfter = retryAfter;
  }
}

/**
 * Storage helpers for Bearer token
 */
const TOKEN_KEY = "payguard_access_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeStoredToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
}

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  skipAuth?: boolean;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 20000, skipAuth = false, headers = {}, ...rest } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const isFormData = typeof FormData !== "undefined" && rest.body instanceof FormData;
  const requestHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(headers as Record<string, string>),
  };
  if (!isFormData) {
    requestHeaders["Content-Type"] = "application/json";
  }

  if (!skipAuth) {
    const token = getStoredToken();
    if (token) {
      requestHeaders["Authorization"] = `Bearer ${token}`;
    }
  }

  // Ensure leading slash
  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${API_BASE_URL}${cleanEndpoint}`;

  try {
    const response = await fetch(url, {
      ...rest,
      headers: requestHeaders,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // Rate Limit check
    const retryAfterHeader = response.headers.get("Retry-After");
    const retryAfter = retryAfterHeader ? parseInt(retryAfterHeader, 10) : null;

    if (!response.ok) {
      let errorMessage = `Request failed with status ${response.status}`;
      let errorCode = "UNKNOWN_ERROR";
      let errorField: string | null = null;

      try {
        const errorData: ApiErrorEnvelope | any = await response.json();
        if (errorData && errorData.error) {
          errorCode = errorData.error.code || errorCode;
          errorMessage = errorData.error.message || errorMessage;
          errorField = errorData.error.field || null;
        } else if (errorData && errorData.detail) {
          // Standard FastAPI fallback
          if (Array.isArray(errorData.detail)) {
            errorCode = "VALIDATION_ERROR";
            errorMessage = errorData.detail.map((d: any) => `${d.loc?.join(".")}: ${d.msg}`).join("; ");
          } else {
            errorMessage = String(errorData.detail);
          }
        }
      } catch {
        // Plain text or unparsable error response
        const text = await response.text().catch(() => "");
        if (text) errorMessage = text;
      }

      if (response.status === 401) {
        // Session expired or invalid
        removeStoredToken();
        throw new ApiError(errorMessage || "Session expired or invalid credentials. Please log in again.", 401, errorCode);
      }

      if (response.status === 403) {
        throw new ApiError(errorMessage || "You do not have permission to perform this action.", 403, errorCode);
      }

      if (response.status === 404) {
        throw new ApiError(errorMessage || "Requested resource was not found.", 404, errorCode);
      }

      if (response.status === 429) {
        const waitMessage = retryAfter ? ` Please wait ${retryAfter} seconds before retrying.` : "";
        throw new ApiError(
          errorMessage || `Rate limit exceeded.${waitMessage}`,
          429,
          "RATE_LIMIT_EXCEEDED",
          null,
          retryAfter
        );
      }

      throw new ApiError(errorMessage, response.status, errorCode, errorField, retryAfter);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (err: any) {
    clearTimeout(timeoutId);

    if (err.name === "AbortError") {
      throw new ApiError("Request timed out. The server took too long to respond.", 408, "TIMEOUT");
    }

    if (err instanceof ApiError) {
      throw err;
    }

    throw new ApiError(
      err.message || "Network error. Unable to communicate with the PayGuard AI backend.",
      0,
      "NETWORK_ERROR"
    );
  }
}

/**
 * PayGuard AI API Resource Methods
 */
export const api = {
  // Health
  async getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>("/health", { skipAuth: true, timeoutMs: 5000 });
  },

  // Auth
  async login(credentials: { email: string; password: string }): Promise<TokenResponse> {
    const res = await request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
      skipAuth: true,
    });
    if (res.access_token) {
      setStoredToken(res.access_token);
    }
    return res;
  },

  async register(data: {
    email: string;
    password: string;
    full_name: string;
    role?: string;
  }): Promise<User> {
    return request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
      skipAuth: true,
    });
  },

  async getMe(): Promise<User> {
    return request<User>("/auth/me");
  },

  logout(): void {
    removeStoredToken();
  },

  // Payments
  async listPayments(params: {
    payment_reference?: string;
    customer_id?: string;
    merchant_id?: string;
    status?: string;
    payment_method?: string;
    gateway_name?: string;
    page?: number;
    page_size?: number;
  } = {}): Promise<PaginatedResponse<PaymentSummary>> {
    const query = new URLSearchParams();
    if (params.payment_reference) query.append("payment_reference", params.payment_reference);
    if (params.customer_id) query.append("customer_id", params.customer_id);
    if (params.merchant_id) query.append("merchant_id", params.merchant_id);
    if (params.status) query.append("status", params.status);
    if (params.payment_method) query.append("payment_method", params.payment_method);
    if (params.gateway_name) query.append("gateway_name", params.gateway_name);
    if (params.page) query.append("page", String(params.page));
    if (params.page_size) query.append("page_size", String(params.page_size));

    const qs = query.toString();
    return request<PaginatedResponse<PaymentSummary>>(`/payments${qs ? `?${qs}` : ""}`);
  },

  async getPayment(paymentId: string): Promise<PaymentDetail> {
    return request<PaymentDetail>(`/payments/${paymentId}`);
  },

  async getPaymentByReference(reference: string): Promise<PaymentDetail> {
    return request<PaymentDetail>(`/payments/by-reference/${encodeURIComponent(reference)}`);
  },

  // Investigations
  async getMetrics(): Promise<InvestigationMetrics> {
    return request<InvestigationMetrics>("/investigations/metrics");
  },

  async listInvestigations(params: {
    status?: string;
    priority?: string;
    page?: number;
    page_size?: number;
  } = {}): Promise<PaginatedResponse<InvestigationCase>> {
    const query = new URLSearchParams();
    if (params.status) query.append("status", params.status);
    if (params.priority) query.append("priority", params.priority);
    if (params.page) query.append("page", String(params.page));
    if (params.page_size) query.append("page_size", String(params.page_size));

    const qs = query.toString();
    return request<PaginatedResponse<InvestigationCase>>(`/investigations${qs ? `?${qs}` : ""}`);
  },

  async getInvestigation(id: string): Promise<InvestigationCase> {
    return request<InvestigationCase>(`/investigations/${id}`);
  },

  async createInvestigation(payload: InvestigationCreateRequest): Promise<InvestigationCase> {
    return request<InvestigationCase>("/investigations", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 60000,
    });
  },

  // Knowledge & Hybrid Search
  async searchKnowledge(payload: {
    query: string;
    top_k?: number;
    retrieval_mode?: "hybrid" | "semantic_only" | "lexical_only";
    doc_type?: string;
    min_score?: number;
    document_ids?: string[];
    scope?: string;
  }): Promise<KnowledgeSearchResponse> {
    return request<KnowledgeSearchResponse>("/knowledge/search", {
      method: "POST",
      body: JSON.stringify({
        query: payload.query,
        top_k: payload.top_k ?? 5,
        retrieval_mode: payload.retrieval_mode ?? "hybrid",
        doc_type: payload.doc_type || undefined,
        min_score: payload.min_score || undefined,
        document_ids: payload.document_ids || undefined,
        scope: payload.scope || "all",
      }),
    });
  },

  // User-Uploaded Documents & Grounded QA
  async uploadDocument(file: File, title?: string, docType?: string): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    if (title) formData.append("title", title);
    if (docType) formData.append("doc_type", docType);

    return request<DocumentUploadResponse>("/knowledge/upload", {
      method: "POST",
      body: formData,
      timeoutMs: 90000,
    });
  },

  async listDocuments(scope: string = "uploaded", page: number = 1, pageSize: number = 20): Promise<UserDocumentSummary[]> {
    const qs = new URLSearchParams({
      scope,
      page: String(page),
      page_size: String(pageSize),
    }).toString();
    return request<UserDocumentSummary[]>(`/knowledge/documents?${qs}`);
  },

  async getDocument(id: string): Promise<UserDocumentDetail> {
    return request<UserDocumentDetail>(`/knowledge/documents/${id}`);
  },

  async deleteDocument(id: string): Promise<{ success: boolean; message: string }> {
    return request<{ success: boolean; message: string }>(`/knowledge/documents/${id}`, {
      method: "DELETE",
    });
  },

  async askDocumentQuestion(payload: {
    query: string;
    document_ids?: string[];
    scope?: string;
    top_k?: number;
    retrieval_mode?: string;
  }): Promise<DocumentAskResponse> {
    return request<DocumentAskResponse>("/knowledge/ask", {
      method: "POST",
      body: JSON.stringify({
        query: payload.query,
        document_ids: payload.document_ids || undefined,
        scope: payload.scope || "uploaded",
        top_k: payload.top_k ?? 5,
        retrieval_mode: payload.retrieval_mode ?? "hybrid",
      }),
      timeoutMs: 60000,
    });
  },
};

