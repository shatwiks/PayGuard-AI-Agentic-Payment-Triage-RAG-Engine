"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  BookOpen,
  Search,
  Sparkles,
  ExternalLink,
  Loader2,
  FileText,
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  Trash2,
  HelpCircle,
  FileCheck,
  RefreshCw,
  Eye,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import {
  DocumentAskResponse,
  DocumentUploadResponse,
  SearchResultItem,
  UserDocumentDetail,
  UserDocumentSummary,
} from "@/lib/types";
import { ErrorAlert } from "@/components/ui/ErrorAlert";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EvidenceDrawer, EvidenceDrawerItem } from "@/components/ui/EvidenceDrawer";
import { useToast } from "@/components/ui/ToastContext";

export default function KnowledgePage() {
  const { addToast } = useToast();
  const [activeTab, setActiveTab] = useState<"search" | "ask" | "documents">(
    "search"
  );

  // Document Management State
  const [documents, setDocuments] = useState<UserDocumentSummary[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [docDetail, setDocDetail] = useState<UserDocumentDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  // Delete Confirmation Modal State
  const [docPendingDelete, setDocPendingDelete] = useState<{
    id: string;
    title: string;
  } | null>(null);
  const [isDeletingDoc, setIsDeletingDoc] = useState(false);

  // Evidence Drawer State
  const [drawerEvidence, setDrawerEvidence] =
    useState<EvidenceDrawerItem | null>(null);

  // Upload State
  const [fileToUpload, setFileToUpload] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadDocType, setUploadDocType] = useState("general_compliance");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] =
    useState<DocumentUploadResponse | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Grounded QA State
  const [qaQuery, setQaQuery] = useState("");
  const [qaScope, setQaScope] = useState<
    "uploaded" | "knowledge_base" | "all"
  >("all");
  const [qaTargetDocId, setQaTargetDocId] = useState<string>("all");
  const [isAsking, setIsAsking] = useState(false);
  const [qaResponse, setQaResponse] = useState<DocumentAskResponse | null>(
    null
  );
  const [qaError, setQaError] = useState<string | null>(null);

  // Policy Search State (Rule Explorer)
  const [query, setQuery] = useState("");
  const [retrievalMode, setRetrievalMode] = useState<
    "hybrid" | "semantic_only" | "lexical_only"
  >("hybrid");
  const [searchDocType, setSearchDocType] = useState<string>("");
  const [topK, setTopK] = useState<number>(5);
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [totalCandidates, setTotalCandidates] = useState<number | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchError, setSearchError] = useState<{
    message: string;
    code?: string;
    retryAfter?: number | null;
  } | null>(null);

  // Fetch documents on mount
  const fetchDocuments = useCallback(async () => {
    setIsLoadingDocs(true);
    try {
      const data = await api.listDocuments("uploaded");
      setDocuments(data || []);
    } catch {
      // Non-blocking on initial mount
    } finally {
      setIsLoadingDocs(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Handle File Selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUploadError(null);
    setUploadSuccess(null);
    const files = e.target.files;
    if (!files || files.length === 0) {
      setFileToUpload(null);
      return;
    }
    const file = files[0];
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (ext !== ".pdf" && ext !== ".txt") {
      setUploadError(
        "Unsupported format. Only PDF (.pdf) and Plain Text (.txt) files are supported."
      );
      setFileToUpload(null);
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setUploadError(
        `File exceeds maximum size limit of 10 MB (selected: ${(
          file.size /
          (1024 * 1024)
        ).toFixed(1)} MB).`
      );
      setFileToUpload(null);
      return;
    }
    setFileToUpload(file);
    if (!uploadTitle) {
      setUploadTitle(file.name.replace(/\.[^/.]+$/, ""));
    }
  };

  // Handle Document Upload Submission
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fileToUpload) return;

    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const res = await api.uploadDocument(
        fileToUpload,
        uploadTitle || undefined,
        uploadDocType
      );
      setUploadSuccess(res);
      setFileToUpload(null);
      setUploadTitle("");
      addToast(`Uploaded and indexed "${res.title}"`, "success");
      await fetchDocuments();
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Failed to upload and process document.";
      setUploadError(msg);
      addToast(msg, "error");
    } finally {
      setIsUploading(false);
    }
  };

  // View Document Details
  const handleViewDetail = async (id: string) => {
    setSelectedDocId(id);
    setIsLoadingDetail(true);
    try {
      const detail = await api.getDocument(id);
      setDocDetail(detail);
    } catch {
      addToast("Failed to load document metadata", "error");
    } finally {
      setIsLoadingDetail(false);
    }
  };

  // Confirm Delete Document
  const handleConfirmDeleteDocument = async () => {
    if (!docPendingDelete) return;
    setIsDeletingDoc(true);
    try {
      await api.deleteDocument(docPendingDelete.id);
      if (selectedDocId === docPendingDelete.id) {
        setDocDetail(null);
        setSelectedDocId(null);
      }
      addToast(`Deleted "${docPendingDelete.title}"`, "success");
      setDocPendingDelete(null);
      await fetchDocuments();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to delete document.";
      addToast(msg, "error");
    } finally {
      setIsDeletingDoc(false);
    }
  };

  // Handle Grounded Question Answering
  const handleAskQuestion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!qaQuery.trim()) return;

    setIsAsking(true);
    setQaError(null);
    setQaResponse(null);

    try {
      const docIds = qaTargetDocId !== "all" ? [qaTargetDocId] : undefined;
      const res = await api.askDocumentQuestion({
        query: qaQuery.trim(),
        document_ids: docIds,
        scope: qaScope,
        top_k: 5,
        retrieval_mode: "hybrid",
      });
      setQaResponse(res);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Failed to synthesize evidence-grounded answer.";
      setQaError(msg);
    } finally {
      setIsAsking(false);
    }
  };

  // Handle Rule Explorer Search
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || query.trim().length < 2) return;

    setIsSearching(true);
    setSearchError(null);
    setHasSearched(true);

    try {
      const response = await api.searchKnowledge({
        query: query.trim(),
        top_k: topK,
        retrieval_mode: retrievalMode,
        doc_type: searchDocType || undefined,
        scope: "all",
      });
      setSearchResults(response.results || []);
      setTotalCandidates(response.total_candidates);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setSearchError({
          message: err.message,
          code: err.code,
          retryAfter: err.retryAfter,
        });
      } else {
        setSearchError({
          message: "Unable to complete knowledge search request.",
        });
      }
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <span className="text-[11px] font-mono uppercase tracking-widest text-[#C6F36A] block mb-1">
            pgvector + Full-Text Search RRF
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-[#F3F5F7]">
            Knowledge Base — Payment Policy &amp; Rule Explorer
          </h1>
          <p className="text-xs text-[#9BA5B0] mt-1">
            Explore authoritative payment rules, ask evidence-grounded questions with deterministic abstention, and ingest custom compliance documents.
          </p>
        </div>

        {/* Tab Navigation */}
        <div
          role="tablist"
          aria-label="Knowledge Base Sections"
          className="inline-flex items-center bg-[#111519] p-1 rounded-xl border border-[#1F262E] self-start lg:self-auto"
        >
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "search"}
            onClick={() => setActiveTab("search")}
            className={`px-3.5 py-2 text-xs font-semibold rounded-lg transition flex items-center gap-1.5 ${
              activeTab === "search"
                ? "bg-[#C6F36A] text-[#0B0D0F] shadow-xs"
                : "text-[#9BA5B0] hover:text-[#F3F5F7]"
            }`}
          >
            <Search className="w-3.5 h-3.5" />
            Rule Explorer
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "ask"}
            onClick={() => setActiveTab("ask")}
            className={`px-3.5 py-2 text-xs font-semibold rounded-lg transition flex items-center gap-1.5 ${
              activeTab === "ask"
                ? "bg-[#C6F36A] text-[#0B0D0F] shadow-xs"
                : "text-[#9BA5B0] hover:text-[#F3F5F7]"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            Grounded Q&amp;A
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "documents"}
            onClick={() => setActiveTab("documents")}
            className={`px-3.5 py-2 text-xs font-semibold rounded-lg transition flex items-center gap-1.5 ${
              activeTab === "documents"
                ? "bg-[#C6F36A] text-[#0B0D0F] shadow-xs"
                : "text-[#9BA5B0] hover:text-[#F3F5F7]"
            }`}
          >
            <UploadCloud className="w-3.5 h-3.5" />
            Upload &amp; Manage
            {documents.length > 0 && (
              <span
                className={`ml-1 px-1.5 py-0.2 rounded text-[10px] font-mono tabular-nums ${
                  activeTab === "documents"
                    ? "bg-[#0B0D0F]/20 text-[#0B0D0F]"
                    : "bg-[#171C21] text-[#C6F36A]"
                }`}
              >
                {documents.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* TAB 1: RULE EXPLORER (SEARCH) */}
      {activeTab === "search" && (
        <div className="space-y-6">
          {searchError && (
            <ErrorAlert
              message={searchError.message}
              code={searchError.code}
              retryAfter={searchError.retryAfter}
            />
          )}

          <div className="pg-surface-shell">
            <div className="pg-surface-core p-6 space-y-4">
              <form onSubmit={handleSearch} className="space-y-4">
                <div className="relative">
                  <Search className="w-5 h-5 text-[#6E7A87] absolute left-3.5 top-3.5 pointer-events-none" />
                  <input
                    type="text"
                    required
                    placeholder="Query regulatory rules, dispute condition codes, or failure handling guidelines..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    className="w-full pl-11 pr-32 py-3 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-sm text-[#F3F5F7] placeholder-[#6E7A87] focus:outline-none focus:border-[#C6F36A] transition"
                  />
                  <button
                    type="submit"
                    disabled={isSearching || query.trim().length < 2}
                    className="absolute right-2 top-2 px-4 py-2 bg-[#C6F36A] hover:bg-[#D4F788] text-[#0B0D0F] font-semibold text-xs rounded-lg disabled:opacity-40 transition flex items-center"
                  >
                    {isSearching ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                        Searching...
                      </>
                    ) : (
                      "Search RAG"
                    )}
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
                  <div>
                    <label
                      htmlFor="retrieval-mode-select"
                      className="block text-xs font-medium text-[#9BA5B0] mb-1.5"
                    >
                      Retrieval Engine
                    </label>
                    <select
                      id="retrieval-mode-select"
                      value={retrievalMode}
                      onChange={(e) =>
                        setRetrievalMode(
                          e.target.value as
                            | "hybrid"
                            | "semantic_only"
                            | "lexical_only"
                        )
                      }
                      className="w-full px-3 py-2 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-xs text-[#F3F5F7] focus:outline-none focus:border-[#C6F36A] transition"
                    >
                      <option value="hybrid">
                        Hybrid (pgvector + FTS RRF)
                      </option>
                      <option value="semantic_only">
                        Semantic Only (pgvector Cosine)
                      </option>
                      <option value="lexical_only">
                        Lexical Only (PostgreSQL FTS)
                      </option>
                    </select>
                  </div>

                  <div>
                    <label
                      htmlFor="doc-category-select"
                      className="block text-xs font-medium text-[#9BA5B0] mb-1.5"
                    >
                      Document Category
                    </label>
                    <select
                      id="doc-category-select"
                      value={searchDocType}
                      onChange={(e) => setSearchDocType(e.target.value)}
                      className="w-full px-3 py-2 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-xs text-[#F3F5F7] focus:outline-none focus:border-[#C6F36A] transition"
                    >
                      <option value="">All Document Types</option>
                      <option value="scheme_rules">
                        Scheme Rules (Visa, Mastercard, NACHA)
                      </option>
                      <option value="refund_policy">
                        Refund &amp; Reversal Policies
                      </option>
                      <option value="dispute_guide">Dispute Guidelines</option>
                      <option value="sla_spec">
                        SLA &amp; Settlement Specifications
                      </option>
                    </select>
                  </div>

                  <div>
                    <label
                      htmlFor="top-k-range"
                      className="block text-xs font-medium text-[#9BA5B0] mb-1.5 font-mono tabular-nums"
                    >
                      Top Candidates (K: {topK})
                    </label>
                    <input
                      id="top-k-range"
                      type="range"
                      min={1}
                      max={20}
                      value={topK}
                      onChange={(e) => setTopK(parseInt(e.target.value, 10))}
                      className="w-full h-2 bg-[#0B0D0F] border border-[#262F38] rounded-lg appearance-none cursor-pointer mt-2 accent-[#C6F36A]"
                    />
                  </div>
                </div>
              </form>
            </div>
          </div>

          {/* Results Section */}
          {hasSearched && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between text-xs text-[#9BA5B0] gap-2">
                <span>
                  Found{" "}
                  <strong className="text-[#F3F5F7] font-mono tabular-nums">
                    {searchResults.length}
                  </strong>{" "}
                  ranked policy chunks{" "}
                  {totalCandidates !== null &&
                    `(evaluated ${totalCandidates} total candidates)`}
                </span>
                <span className="font-mono bg-[#111519] border border-[#1F262E] px-2.5 py-1 rounded-md text-[#C6F36A]">
                  Mode: {retrievalMode}
                </span>
              </div>

              {searchResults.length === 0 ? (
                <EmptyState
                  title="No policy chunks matched"
                  description="Try broadening your search terms or changing the retrieval mode."
                />
              ) : (
                <div className="space-y-4">
                  {searchResults.map((item) => (
                    <div key={item.chunk_id} className="pg-surface-shell">
                      <div className="pg-surface-core p-6 space-y-4">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-3 border-b border-[#1F262E] gap-2">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <FileText className="w-4 h-4 text-[#C6F36A]" />
                              <h3 className="text-sm font-bold text-[#F3F5F7]">
                                {item.title}
                              </h3>
                              <span className="text-[11px] font-mono text-[#2DD4BF] bg-[#2DD4BF]/10 px-2 py-0.5 rounded border border-[#2DD4BF]/25">
                                {item.doc_type}
                              </span>
                            </div>
                            <span className="text-xs font-mono text-[#9BA5B0] mt-1 block tabular-nums">
                              {item.section_header} • Chunk #{item.chunk_index}{" "}
                              ({item.token_count} tokens)
                            </span>
                          </div>

                          <div className="flex items-center gap-3">
                            <div className="text-right">
                              <span className="text-[10px] text-[#6E7A87] uppercase tracking-wider block font-mono">
                                Fusion Score
                              </span>
                              <span className="text-sm font-mono font-bold text-[#C6F36A] tabular-nums">
                                {item.ranking.fusion_score.toFixed(4)}
                              </span>
                            </div>
                            <button
                              type="button"
                              onClick={() =>
                                setDrawerEvidence({
                                  title: item.title,
                                  section: item.section_header,
                                  excerpt: item.content,
                                  chunkId: item.chunk_id,
                                  score: item.ranking.fusion_score,
                                  scoreLabel: "RRF Fusion Score",
                                  sourceId: item.source_id,
                                  sourceUrl: item.source_url,
                                  docType: item.doc_type,
                                  retrievalMode,
                                })
                              }
                              className="px-3 py-1.5 rounded-lg bg-[#171C21] border border-[#262F38] hover:border-[#C6F36A]/50 text-xs font-mono text-[#F3F5F7] transition"
                            >
                              Inspect
                            </button>
                          </div>
                        </div>

                        <div className="p-4 bg-[#0B0D0F] rounded-xl border border-[#1F262E] text-xs text-[#F3F5F7] leading-relaxed whitespace-pre-wrap">
                          {item.content}
                        </div>

                        <div className="pt-1 flex flex-wrap items-center justify-between text-[11px] text-[#6E7A87] font-mono gap-2 tabular-nums">
                          <div className="flex flex-wrap gap-4">
                            {item.ranking.semantic_similarity != null && (
                              <span>
                                Cosine Similarity:{" "}
                                <strong className="text-[#9BA5B0]">
                                  {(
                                    item.ranking.semantic_similarity * 100
                                  ).toFixed(1)}
                                  %
                                </strong>
                              </span>
                            )}
                            {item.ranking.lexical_rank != null && (
                              <span>
                                FTS Rank:{" "}
                                <strong className="text-[#9BA5B0]">
                                  #{item.ranking.lexical_rank}
                                </strong>
                              </span>
                            )}
                            {item.ranking.semantic_rank != null && (
                              <span>
                                Vector Rank:{" "}
                                <strong className="text-[#9BA5B0]">
                                  #{item.ranking.semantic_rank}
                                </strong>
                              </span>
                            )}
                          </div>

                          {item.source_url && (
                            <a
                              href={item.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[#C6F36A] hover:underline flex items-center"
                            >
                              Source Document
                              <ExternalLink className="w-3 h-3 ml-1" />
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: GROUNDED DOCUMENT QUESTION ANSWERING */}
      {activeTab === "ask" && (
        <div className="space-y-6">
          <div className="pg-surface-shell">
            <div className="pg-surface-core p-6 space-y-4">
              <div className="flex flex-wrap items-center justify-between pb-3 border-b border-[#1F262E] gap-2">
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-5 h-5 text-[#C6F36A]" />
                  <h2 className="text-base font-bold text-[#F3F5F7]">
                    Document-Grounded Question Answering
                  </h2>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-[#2DD4BF] bg-[#2DD4BF]/10 px-2.5 py-1 rounded-full border border-[#2DD4BF]/25 font-mono">
                  <ShieldCheck className="w-3.5 h-3.5 text-[#2DD4BF]" />
                  Hallucination-Protected QA
                </div>
              </div>

              <p className="text-xs text-[#9BA5B0]">
                Ask questions directly against your uploaded documents or authoritative payment schemes. Answers are synthesized strictly from retrieved evidence with verifiable page and chunk citations, and abstain deterministically when unsupported.
              </p>

              {qaError && <ErrorAlert message={qaError} />}

              <form onSubmit={handleAskQuestion} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label
                      htmlFor="qa-scope-select"
                      className="block text-xs font-medium text-[#9BA5B0] mb-1.5"
                    >
                      Knowledge Scope
                    </label>
                    <select
                      id="qa-scope-select"
                      value={qaScope}
                      onChange={(e) =>
                        setQaScope(
                          e.target.value as
                            | "uploaded"
                            | "knowledge_base"
                            | "all"
                        )
                      }
                      className="w-full px-3 py-2 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-xs text-[#F3F5F7] focus:outline-none focus:border-[#C6F36A] transition"
                    >
                      <option value="all">
                        Combined Knowledge (Uploaded + Scheme Rules)
                      </option>
                      <option value="knowledge_base">
                        System Knowledge Base (Scheme Rules Only)
                      </option>
                      <option value="uploaded">
                        My Uploaded Documents Only
                      </option>
                    </select>
                  </div>

                  <div>
                    <label
                      htmlFor="qa-target-doc"
                      className="block text-xs font-medium text-[#9BA5B0] mb-1.5"
                    >
                      Target Document
                    </label>
                    <select
                      id="qa-target-doc"
                      value={qaTargetDocId}
                      onChange={(e) => setQaTargetDocId(e.target.value)}
                      className="w-full px-3 py-2 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-xs text-[#F3F5F7] focus:outline-none focus:border-[#C6F36A] transition"
                    >
                      <option value="all">
                        All Documents in Selected Scope
                      </option>
                      {documents.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.title} ({d.file_name || "file"})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="relative">
                  <HelpCircle className="w-5 h-5 text-[#6E7A87] absolute left-3.5 top-3.5 pointer-events-none" />
                  <input
                    type="text"
                    required
                    placeholder="e.g. What is the maximum fee for a standard refund request?"
                    value={qaQuery}
                    onChange={(e) => setQaQuery(e.target.value)}
                    className="w-full pl-11 pr-36 py-3 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-sm text-[#F3F5F7] placeholder-[#6E7A87] focus:outline-none focus:border-[#C6F36A] transition"
                  />
                  <button
                    type="submit"
                    disabled={isAsking || !qaQuery.trim()}
                    className="absolute right-2 top-2 px-4 py-2 bg-[#C6F36A] hover:bg-[#D4F788] text-[#0B0D0F] font-semibold text-xs rounded-lg disabled:opacity-40 transition flex items-center gap-1.5"
                  >
                    {isAsking ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Answering...
                      </>
                    ) : (
                      "Ask Grounded AI"
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>

          {/* QA Answer Response Card */}
          {qaResponse && (
            <div className="pg-surface-shell">
              <div className="pg-surface-core p-6 space-y-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#1F262E] gap-2">
                  <div className="flex items-center space-x-3">
                    {qaResponse.is_grounded ? (
                      <div className="w-8 h-8 rounded-xl bg-[#2DD4BF]/10 border border-[#2DD4BF]/30 flex items-center justify-center text-[#2DD4BF] shrink-0">
                        <CheckCircle2 className="w-4 h-4" />
                      </div>
                    ) : (
                      <div className="w-8 h-8 rounded-xl bg-[#F59E0B]/10 border border-[#F59E0B]/30 flex items-center justify-center text-[#F59E0B] shrink-0">
                        <AlertCircle className="w-4 h-4" />
                      </div>
                    )}
                    <div>
                      <h3 className="text-sm font-bold text-[#F3F5F7]">
                        {qaResponse.is_grounded
                          ? "Evidence-Grounded Answer"
                          : "Fact Absent / Deterministic Abstention"}
                      </h3>
                      <span className="text-[11px] font-mono text-[#6E7A87]">
                        Mode: {qaResponse.retrieval_mode_used} • Embeddings:{" "}
                        {qaResponse.embedding_status}
                      </span>
                    </div>
                  </div>

                  <span
                    className={`text-[11px] font-mono px-2.5 py-1 rounded-md border ${
                      qaResponse.is_grounded
                        ? "bg-[#2DD4BF]/10 text-[#2DD4BF] border-[#2DD4BF]/30 font-semibold"
                        : "bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30 font-semibold"
                    }`}
                  >
                    {qaResponse.is_grounded
                      ? "VERIFIED GROUNDED"
                      : "FACT NOT FOUND"}
                  </span>
                </div>

                {/* Synthesized Answer */}
                <div
                  className={`p-4 rounded-xl border text-sm leading-relaxed whitespace-pre-wrap ${
                    qaResponse.is_grounded
                      ? "bg-[#0B0D0F] border-[#1F262E] text-[#F3F5F7]"
                      : "bg-[#F59E0B]/5 border-[#F59E0B]/30 text-[#F3F5F7]"
                  }`}
                >
                  {qaResponse.answer}
                </div>

                {/* Citations List */}
                {qaResponse.citations && qaResponse.citations.length > 0 && (
                  <div className="space-y-3 pt-1">
                    <h4 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#9BA5B0] flex items-center gap-1.5">
                      <BookOpen className="w-3.5 h-3.5 text-[#C6F36A]" />
                      Source Provenance &amp; Verifiable Citations (
                      {qaResponse.citations.length})
                    </h4>

                    <div className="space-y-2.5">
                      {qaResponse.citations.map((cit, idx) => (
                        <button
                          type="button"
                          key={idx}
                          onClick={() =>
                            setDrawerEvidence({
                              title: cit.document_name,
                              section: cit.section,
                              excerpt: cit.excerpt,
                              page: cit.page,
                              chunkId: cit.chunk_id,
                              retrievalMode: qaResponse.retrieval_mode_used,
                            })
                          }
                          className="w-full text-left p-3.5 bg-[#0B0D0F] hover:bg-[#171C21]/70 rounded-xl border border-[#1F262E] hover:border-[#C6F36A]/50 text-xs space-y-1.5 transition group"
                        >
                          <div className="flex flex-wrap items-center justify-between text-[11px] font-mono text-[#9BA5B0] gap-2">
                            <span className="font-bold text-[#F3F5F7] group-hover:text-[#C6F36A] flex items-center gap-1.5 transition">
                              <FileText className="w-3.5 h-3.5 text-[#C6F36A]" />
                              {cit.document_name}
                            </span>
                            <span>Section: {cit.section}</span>
                            {cit.page && <span>Page #{cit.page}</span>}
                            <span className="text-[#6E7A87] text-[10px]">
                              Chunk: {cit.chunk_id.substring(0, 8)}...
                            </span>
                          </div>
                          <p className="text-[#9BA5B0] italic border-l-2 border-[#C6F36A]/50 pl-2.5">
                            &ldquo;{cit.excerpt}&rdquo;
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: UPLOAD & MANAGE DOCUMENTS */}
      {activeTab === "documents" && (
        <div className="space-y-6">
          {/* Upload Dropzone Card */}
          <div className="pg-surface-shell">
            <div className="pg-surface-core p-6 space-y-4">
              <div className="flex flex-wrap items-center justify-between pb-3 border-b border-[#1F262E] gap-2">
                <div className="flex items-center space-x-2">
                  <UploadCloud className="w-5 h-5 text-[#C6F36A]" />
                  <h2 className="text-base font-bold text-[#F3F5F7]">
                    Upload Compliance Document
                  </h2>
                </div>
                <div className="flex items-center space-x-2 text-xs font-mono text-[#9BA5B0]">
                  <span className="bg-[#171C21] text-[#C6F36A] px-2 py-0.5 rounded border border-[#262F38]">
                    PDF (.pdf)
                  </span>
                  <span className="bg-[#171C21] text-[#9BA5B0] px-2 py-0.5 rounded border border-[#262F38]">
                    Plain Text (.txt)
                  </span>
                  <span className="bg-[#171C21] text-[#9BA5B0] px-2 py-0.5 rounded border border-[#262F38]">
                    Max 10 MB
                  </span>
                </div>
              </div>

              {uploadError && (
                <div
                  role="alert"
                  className="p-3.5 bg-[#F87171]/10 border border-[#F87171]/30 rounded-xl flex items-center text-xs text-[#F87171] gap-2"
                >
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{uploadError}</span>
                </div>
              )}

              {uploadSuccess && (
                <div className="p-3.5 bg-[#2DD4BF]/10 border border-[#2DD4BF]/30 rounded-xl flex items-start text-xs text-[#F3F5F7] gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-[#2DD4BF] shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-semibold text-[#2DD4BF]">
                      {uploadSuccess.message}
                    </p>
                    <p className="text-[11px] text-[#9BA5B0] font-mono tabular-nums">
                      Document: <strong>{uploadSuccess.file_name}</strong> •
                      Pages: {uploadSuccess.page_count} • Chunks:{" "}
                      {uploadSuccess.chunks_created} • Processing:{" "}
                      <span className="uppercase text-[#2DD4BF]">
                        {uploadSuccess.processing_status}
                      </span>{" "}
                      • Embeddings:{" "}
                      <span className="uppercase text-[#C6F36A]">
                        {uploadSuccess.embedding_status}
                      </span>
                    </p>
                  </div>
                </div>
              )}

              <form onSubmit={handleUploadSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label
                      htmlFor="upload-title-input"
                      className="block text-xs font-medium text-[#9BA5B0] mb-1.5"
                    >
                      Document Title (Optional)
                    </label>
                    <input
                      id="upload-title-input"
                      type="text"
                      placeholder="e.g. Fedwire SLA Specification 2026"
                      value={uploadTitle}
                      onChange={(e) => setUploadTitle(e.target.value)}
                      className="w-full px-3.5 py-2 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-xs text-[#F3F5F7] placeholder-[#6E7A87] focus:outline-none focus:border-[#C6F36A] transition"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="upload-category-select"
                      className="block text-xs font-medium text-[#9BA5B0] mb-1.5"
                    >
                      Compliance Category
                    </label>
                    <select
                      id="upload-category-select"
                      value={uploadDocType}
                      onChange={(e) => setUploadDocType(e.target.value)}
                      className="w-full px-3.5 py-2 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-xs text-[#F3F5F7] focus:outline-none focus:border-[#C6F36A] transition"
                    >
                      <option value="general_compliance">
                        General Compliance Policy
                      </option>
                      <option value="scheme_rules">
                        Scheme &amp; Network Rulebook
                      </option>
                      <option value="refund_policy">
                        Refund &amp; Reversal Protocol
                      </option>
                      <option value="dispute_guide">
                        Dispute Handling Guideline
                      </option>
                      <option value="sla_spec">
                        SLA &amp; Settlement Agreement
                      </option>
                    </select>
                  </div>
                </div>

                {/* File Input Dropzone */}
                <div className="border-2 border-dashed border-[#262F38] hover:border-[#C6F36A]/50 rounded-xl p-6 text-center transition bg-[#0B0D0F]/70">
                  <input
                    type="file"
                    id="doc-upload-input"
                    accept=".pdf,.txt,text/plain,application/pdf"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <label
                    htmlFor="doc-upload-input"
                    className="cursor-pointer block space-y-2"
                  >
                    <div className="mx-auto w-10 h-10 rounded-xl bg-[#171C21] border border-[#262F38] flex items-center justify-center text-[#C6F36A]">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div>
                      <span className="text-xs font-semibold text-[#C6F36A] hover:underline">
                        Click to choose a file
                      </span>
                      <span className="text-xs text-[#9BA5B0]">
                        {" "}
                        or drag and drop
                      </span>
                    </div>
                    <p className="text-[11px] text-[#6E7A87] font-mono">
                      {fileToUpload ? (
                        <span className="font-semibold text-[#F3F5F7]">
                          Selected: {fileToUpload.name} (
                          {(fileToUpload.size / 1024).toFixed(1)} KB)
                        </span>
                      ) : (
                        "PDF or TXT documents up to 10 MB"
                      )}
                    </p>
                  </label>
                </div>

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={!fileToUpload || isUploading}
                    className="px-5 py-2.5 bg-[#C6F36A] hover:bg-[#D4F788] text-[#0B0D0F] font-semibold text-xs rounded-xl disabled:opacity-40 transition flex items-center gap-2 active:scale-[0.98]"
                  >
                    {isUploading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Parsing, Chunking &amp; Indexing...
                      </>
                    ) : (
                      <>
                        <UploadCloud className="w-4 h-4" />
                        Upload &amp; Ingest Document
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>

          {/* Uploaded Documents List */}
          <div className="pg-surface-shell">
            <div className="pg-surface-core p-6 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-[#1F262E]">
                <div className="flex items-center space-x-2">
                  <FileCheck className="w-5 h-5 text-[#C6F36A]" />
                  <h2 className="text-base font-bold text-[#F3F5F7]">
                    Your Ingested Documents
                  </h2>
                  <span className="text-xs font-mono bg-[#171C21] border border-[#262F38] px-2 py-0.5 rounded text-[#C6F36A] font-bold tabular-nums">
                    {documents.length}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={fetchDocuments}
                  disabled={isLoadingDocs}
                  className="text-xs text-[#9BA5B0] hover:text-[#F3F5F7] flex items-center gap-1.5 font-medium transition"
                >
                  <RefreshCw
                    className={`w-3.5 h-3.5 ${
                      isLoadingDocs ? "animate-spin text-[#C6F36A]" : ""
                    }`}
                  />
                  Refresh
                </button>
              </div>

              {isLoadingDocs ? (
                <div className="py-12 flex flex-col items-center justify-center text-[#9BA5B0] gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-[#C6F36A]" />
                  <span className="text-xs">Loading authorized documents...</span>
                </div>
              ) : documents.length === 0 ? (
                <EmptyState
                  title="No uploaded documents yet"
                  description="Upload custom policies or rulebooks above to index them for grounded question answering."
                />
              ) : (
                <div className="divide-y divide-[#1F262E]">
                  {documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-[#171C21]/60 p-3 rounded-xl transition"
                    >
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <FileText className="w-4 h-4 text-[#C6F36A] shrink-0" />
                          <h3 className="text-sm font-semibold text-[#F3F5F7]">
                            {doc.title}
                          </h3>
                          <span className="text-[11px] font-mono bg-[#171C21] text-[#9BA5B0] px-2 py-0.5 rounded border border-[#262F38]">
                            {doc.doc_type}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-3 text-xs text-[#6E7A87] font-mono tabular-nums">
                          <span>File: {doc.file_name || "document.txt"}</span>
                          {doc.file_size_bytes && (
                            <span>
                              • {(doc.file_size_bytes / 1024).toFixed(1)} KB
                            </span>
                          )}
                          <span>• {doc.page_count || 1} page(s)</span>
                          <span>• {doc.chunk_count} chunk(s)</span>
                          <span>
                            • {new Date(doc.created_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {/* Processing Badge */}
                        <span
                          className={`text-[11px] font-mono font-semibold px-2.5 py-0.5 rounded-md border ${
                            doc.processing_status === "processed"
                              ? "bg-[#2DD4BF]/10 text-[#2DD4BF] border-[#2DD4BF]/30"
                              : doc.processing_status === "failed"
                              ? "bg-[#F87171]/10 text-[#F87171] border-[#F87171]/30"
                              : "bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30"
                          }`}
                        >
                          {doc.processing_status}
                        </span>

                        {/* Embedding Badge */}
                        <span
                          className={`text-[11px] font-mono px-2.5 py-0.5 rounded-md border ${
                            doc.embedding_status === "embedded"
                              ? "bg-[#C6F36A]/10 text-[#C6F36A] border-[#C6F36A]/30"
                              : "bg-[#171C21] text-[#9BA5B0] border-[#262F38]"
                          }`}
                        >
                          {doc.embedding_status}
                        </span>

                        {/* Actions */}
                        <button
                          type="button"
                          onClick={() => {
                            setQaScope("uploaded");
                            setQaTargetDocId(doc.id);
                            setActiveTab("ask");
                          }}
                          className="p-2 text-[#C6F36A] hover:bg-[#171C21] rounded-lg transition"
                          title="Ask questions against this document"
                          aria-label={`Ask questions against ${doc.title}`}
                        >
                          <Sparkles className="w-4 h-4" />
                        </button>

                        <button
                          type="button"
                          onClick={() => handleViewDetail(doc.id)}
                          className="p-2 text-[#9BA5B0] hover:text-[#F3F5F7] hover:bg-[#171C21] rounded-lg transition"
                          title="View document details & preview"
                          aria-label={`View details for ${doc.title}`}
                        >
                          <Eye className="w-4 h-4" />
                        </button>

                        <button
                          type="button"
                          onClick={() =>
                            setDocPendingDelete({
                              id: doc.id,
                              title: doc.title,
                            })
                          }
                          className="p-2 text-[#F87171] hover:bg-[#F87171]/10 rounded-lg transition"
                          title="Permanently delete document"
                          aria-label={`Delete ${doc.title}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Document Detail Modal */}
          {selectedDocId && (
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Document details"
              className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4"
            >
              <div className="bg-[#111519] rounded-2xl border border-[#262F38] max-w-2xl w-full p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
                <div className="flex items-center justify-between pb-3 border-b border-[#1F262E]">
                  <div className="flex items-center space-x-2">
                    <FileText className="w-5 h-5 text-[#C6F36A]" />
                    <h3 className="text-base font-bold text-[#F3F5F7]">
                      {docDetail?.title || "Document Details"}
                    </h3>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedDocId(null);
                      setDocDetail(null);
                    }}
                    aria-label="Close document details"
                    className="text-[#9BA5B0] hover:text-[#F3F5F7] p-1"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                {isLoadingDetail ? (
                  <div className="py-12 flex justify-center">
                    <Loader2 className="w-6 h-6 animate-spin text-[#C6F36A]" />
                  </div>
                ) : docDetail ? (
                  <div className="space-y-4 overflow-y-auto pr-1">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[#0B0D0F] p-3.5 rounded-xl border border-[#1F262E] text-xs font-mono tabular-nums">
                      <div>
                        <span className="text-[#6E7A87] block text-[10px] uppercase">
                          Format
                        </span>
                        <span className="font-semibold text-[#F3F5F7]">
                          {docDetail.mime_type || "text/plain"}
                        </span>
                      </div>
                      <div>
                        <span className="text-[#6E7A87] block text-[10px] uppercase">
                          Size
                        </span>
                        <span className="font-semibold text-[#F3F5F7]">
                          {docDetail.file_size_bytes
                            ? `${(docDetail.file_size_bytes / 1024).toFixed(1)} KB`
                            : "N/A"}
                        </span>
                      </div>
                      <div>
                        <span className="text-[#6E7A87] block text-[10px] uppercase">
                          Pages
                        </span>
                        <span className="font-semibold text-[#F3F5F7]">
                          {docDetail.page_count || 1}
                        </span>
                      </div>
                      <div>
                        <span className="text-[#6E7A87] block text-[10px] uppercase">
                          Chunks
                        </span>
                        <span className="font-semibold text-[#C6F36A]">
                          {docDetail.chunk_count}
                        </span>
                      </div>
                    </div>

                    <div>
                      <span className="text-xs font-mono text-[#9BA5B0] block mb-1">
                        SHA-256 Content Hash
                      </span>
                      <p className="text-[11px] font-mono bg-[#0B0D0F] p-2.5 rounded-xl border border-[#1F262E] break-all text-[#9BA5B0]">
                        {docDetail.content_hash || "N/A"}
                      </p>
                    </div>

                    {docDetail.raw_content_preview && (
                      <div>
                        <span className="text-xs font-mono text-[#9BA5B0] block mb-1">
                          Raw Content Preview
                        </span>
                        <div className="p-3.5 bg-[#0B0D0F] rounded-xl border border-[#1F262E] text-xs text-[#F3F5F7] whitespace-pre-wrap max-h-48 overflow-y-auto">
                          {docDetail.raw_content_preview}
                        </div>
                      </div>
                    )}
                  </div>
                ) : null}

                <div className="flex justify-end pt-3 border-t border-[#1F262E]">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedDocId(null);
                      setDocDetail(null);
                    }}
                    className="px-4 py-2 bg-[#171C21] hover:bg-[#1F262E] text-[#F3F5F7] text-xs font-semibold rounded-xl transition"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Accessible Confirmation Dialog for Document Deletion */}
      <ConfirmDialog
        isOpen={docPendingDelete !== null}
        title="Delete Compliance Document"
        description={
          docPendingDelete
            ? `Are you sure you want to permanently delete "${docPendingDelete.title}" and remove all of its indexed vector chunks? This action cannot be undone.`
            : ""
        }
        confirmLabel="Delete Document"
        cancelLabel="Cancel"
        variant="danger"
        isLoading={isDeletingDoc}
        onConfirm={handleConfirmDeleteDocument}
        onCancel={() => {
          if (!isDeletingDoc) setDocPendingDelete(null);
        }}
      />

      {/* Slide-Over Evidence Drawer */}
      <EvidenceDrawer
        isOpen={drawerEvidence !== null}
        onClose={() => setDrawerEvidence(null)}
        evidence={drawerEvidence}
      />
    </div>
  );
}
