"use client";

import React, { useEffect, useState } from "react";
import {
  BookOpen,
  Search,
  Filter,
  Sparkles,
  ExternalLink,
  Layers,
  Sliders,
  Loader2,
  FileText,
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  Trash2,
  HelpCircle,
  Info,
  Calendar,
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

export default function KnowledgePage() {
  const [activeTab, setActiveTab] = useState<"documents" | "ask" | "search">("documents");

  // Document Management State
  const [documents, setDocuments] = useState<UserDocumentSummary[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [docDetail, setDocDetail] = useState<UserDocumentDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  // Upload State
  const [fileToUpload, setFileToUpload] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadDocType, setUploadDocType] = useState("general_compliance");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<DocumentUploadResponse | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Grounded QA State
  const [qaQuery, setQaQuery] = useState("");
  const [qaScope, setQaScope] = useState<"uploaded" | "knowledge_base" | "all">("uploaded");
  const [qaTargetDocId, setQaTargetDocId] = useState<string>("all");
  const [isAsking, setIsAsking] = useState(false);
  const [qaResponse, setQaResponse] = useState<DocumentAskResponse | null>(null);
  const [qaError, setQaError] = useState<string | null>(null);

  // Policy Search State (Legacy & deep diagnostic explorer)
  const [query, setQuery] = useState("");
  const [retrievalMode, setRetrievalMode] = useState<"hybrid" | "semantic_only" | "lexical_only">("hybrid");
  const [searchDocType, setSearchDocType] = useState<string>("");
  const [topK, setTopK] = useState<number>(5);
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [totalCandidates, setTotalCandidates] = useState<number | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchError, setSearchError] = useState<{ message: string; code?: string; retryAfter?: number | null } | null>(null);

  // Fetch documents on tab change or mount
  const fetchDocuments = async () => {
    setIsLoadingDocs(true);
    try {
      const data = await api.listDocuments("uploaded");
      setDocuments(data || []);
    } catch (err: any) {
      console.error("Failed to load documents:", err);
    } finally {
      setIsLoadingDocs(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

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
      setUploadError("Unsupported format. Only PDF (.pdf) and Plain Text (.txt) files are supported.");
      setFileToUpload(null);
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setUploadError(`File exceeds maximum size limit of 10 MB (selected: ${(file.size / (1024 * 1024)).toFixed(1)} MB).`);
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
      const res = await api.uploadDocument(fileToUpload, uploadTitle || undefined, uploadDocType);
      setUploadSuccess(res);
      setFileToUpload(null);
      setUploadTitle("");
      // Refresh documents table
      await fetchDocuments();
    } catch (err: any) {
      setUploadError(err.message || "Failed to upload and process document.");
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
    } catch (err: any) {
      console.error("Failed to fetch document detail:", err);
    } finally {
      setIsLoadingDetail(false);
    }
  };

  // Delete Document
  const handleDeleteDocument = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to permanently delete '${name}' and its indexed chunks?`)) {
      return;
    }
    try {
      await api.deleteDocument(id);
      if (selectedDocId === id) {
        setDocDetail(null);
        setSelectedDocId(null);
      }
      await fetchDocuments();
    } catch (err: any) {
      alert(`Failed to delete document: ${err.message}`);
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
    } catch (err: any) {
      setQaError(err.message || "Failed to synthesize evidence-grounded answer.");
    } finally {
      setIsAsking(false);
    }
  };

  // Handle Legacy / Rule Explorer Search
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
    } catch (err: any) {
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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Knowledge Base & Document Center</h1>
          <p className="text-sm text-slate-500 mt-1">
            Ingest custom compliance policies, query documents with evidence citations, and explore authoritative payment rules.
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200">
          <button
            onClick={() => setActiveTab("documents")}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition flex items-center gap-1.5 ${
              activeTab === "documents"
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <UploadCloud className="w-3.5 h-3.5 text-blue-600" />
            Upload & Manage
          </button>
          <button
            onClick={() => setActiveTab("ask")}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition flex items-center gap-1.5 ${
              activeTab === "ask"
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-purple-600" />
            Grounded Q&A
          </button>
          <button
            onClick={() => setActiveTab("search")}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition flex items-center gap-1.5 ${
              activeTab === "search"
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Search className="w-3.5 h-3.5 text-emerald-600" />
            Rule Explorer
          </button>
        </div>
      </div>

      {/* TAB 1: UPLOAD & MANAGE DOCUMENTS */}
      {activeTab === "documents" && (
        <div className="space-y-6">
          {/* Upload Dropzone Card */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <UploadCloud className="w-5 h-5 text-blue-600" />
                <h2 className="text-base font-bold text-slate-900">Upload Compliance Document</h2>
              </div>
              <div className="flex items-center space-x-2 text-xs font-mono text-slate-500">
                <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded border border-blue-200">PDF (.pdf)</span>
                <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">Plain Text (.txt)</span>
                <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">Max 10 MB</span>
              </div>
            </div>

            {uploadError && (
              <div className="p-3.5 bg-red-50 border border-red-200 rounded-lg flex items-center text-xs text-red-700 gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            {uploadSuccess && (
              <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-lg flex items-start text-xs text-emerald-800 gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-semibold">{uploadSuccess.message}</p>
                  <p className="text-[11px] text-emerald-700">
                    Document: <strong>{uploadSuccess.file_name}</strong> • Pages: {uploadSuccess.page_count} • Chunks:{" "}
                    {uploadSuccess.chunks_created} • Processing:{" "}
                    <span className="font-mono uppercase">{uploadSuccess.processing_status}</span> • Embeddings:{" "}
                    <span className="font-mono uppercase">{uploadSuccess.embedding_status}</span>
                  </p>
                </div>
              </div>
            )}

            <form onSubmit={handleUploadSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Document Title (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Fedwire SLA Specification 2026"
                    value={uploadTitle}
                    onChange={(e) => setUploadTitle(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Compliance Category
                  </label>
                  <select
                    value={uploadDocType}
                    onChange={(e) => setUploadDocType(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="general_compliance">General Compliance Policy</option>
                    <option value="scheme_rules">Scheme & Network Rulebook</option>
                    <option value="refund_policy">Refund & Reversal Protocol</option>
                    <option value="dispute_guide">Dispute Handling Guideline</option>
                    <option value="sla_spec">SLA & Settlement Agreement</option>
                  </select>
                </div>
              </div>

              {/* File Input Dropzone */}
              <div className="border-2 border-dashed border-slate-300 hover:border-blue-400 rounded-xl p-6 text-center transition bg-slate-50/50">
                <input
                  type="file"
                  id="doc-upload-input"
                  accept=".pdf,.txt,text/plain,application/pdf"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <label htmlFor="doc-upload-input" className="cursor-pointer block space-y-2">
                  <div className="mx-auto w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-sm font-semibold text-blue-600 hover:underline">
                      Click to choose a file
                    </span>
                    <span className="text-xs text-slate-500"> or drag and drop</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    {fileToUpload ? (
                      <span className="font-semibold text-slate-800">
                        Selected: {fileToUpload.name} ({(fileToUpload.size / 1024).toFixed(1)} KB)
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
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs rounded-lg shadow-xs disabled:opacity-50 transition flex items-center gap-2"
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Parsing, Chunking & Indexing...
                    </>
                  ) : (
                    <>
                      <UploadCloud className="w-4 h-4" />
                      Upload & Ingest Document
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>

          {/* Uploaded Documents List */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs space-y-4 p-6">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <FileCheck className="w-5 h-5 text-slate-700" />
                <h2 className="text-base font-bold text-slate-900">Your Ingested Documents</h2>
                <span className="text-xs font-mono bg-slate-100 px-2 py-0.5 rounded text-slate-700 font-bold">
                  {documents.length}
                </span>
              </div>
              <button
                onClick={fetchDocuments}
                disabled={isLoadingDocs}
                className="text-xs text-slate-600 hover:text-slate-900 flex items-center gap-1 font-medium transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoadingDocs ? "animate-spin" : ""}`} />
                Refresh
              </button>
            </div>

            {isLoadingDocs ? (
              <div className="py-12 flex flex-col items-center justify-center text-slate-400 gap-2">
                <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                <span className="text-xs">Loading authorized documents...</span>
              </div>
            ) : documents.length === 0 ? (
              <EmptyState
                title="No uploaded documents yet"
                description="Upload custom policies or rulebooks above to index them for grounded question answering."
              />
            ) : (
              <div className="divide-y divide-slate-100">
                {documents.map((doc) => (
                  <div key={doc.id} className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50/60 p-2 rounded-lg transition">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-blue-600 shrink-0" />
                        <h3 className="text-sm font-semibold text-slate-900">{doc.title}</h3>
                        <span className="text-[11px] font-mono bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                          {doc.doc_type}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 font-mono">
                        <span>File: {doc.file_name || "document.txt"}</span>
                        {doc.file_size_bytes && (
                          <span>• {(doc.file_size_bytes / 1024).toFixed(1)} KB</span>
                        )}
                        <span>• {doc.page_count || 1} page(s)</span>
                        <span>• {doc.chunk_count} chunk(s)</span>
                        <span>• {new Date(doc.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {/* Processing Badge */}
                      <span className={`text-[11px] font-mono font-semibold px-2.5 py-0.5 rounded-full border ${
                        doc.processing_status === "processed"
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : doc.processing_status === "failed"
                          ? "bg-red-50 text-red-700 border-red-200"
                          : "bg-amber-50 text-amber-700 border-amber-200"
                      }`}>
                        {doc.processing_status}
                      </span>

                      {/* Embedding Badge */}
                      <span className={`text-[11px] font-mono px-2 py-0.5 rounded-full border ${
                        doc.embedding_status === "embedded"
                          ? "bg-purple-50 text-purple-700 border-purple-200"
                          : "bg-slate-100 text-slate-600 border-slate-200"
                      }`}>
                        {doc.embedding_status}
                      </span>

                      {/* Actions */}
                      <button
                        onClick={() => {
                          setQaTargetDocId(doc.id);
                          setActiveTab("ask");
                        }}
                        className="p-1.5 text-purple-600 hover:bg-purple-50 rounded-md transition"
                        title="Ask questions against this document"
                      >
                        <Sparkles className="w-4 h-4" />
                      </button>

                      <button
                        onClick={() => handleViewDetail(doc.id)}
                        className="p-1.5 text-slate-600 hover:bg-slate-100 rounded-md transition"
                        title="View document details & preview"
                      >
                        <Eye className="w-4 h-4" />
                      </button>

                      <button
                        onClick={() => handleDeleteDocument(doc.id, doc.title)}
                        className="p-1.5 text-red-600 hover:bg-red-50 rounded-md transition"
                        title="Permanently delete document"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Document Detail Modal */}
          {selectedDocId && (
            <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
              <div className="bg-white rounded-xl border border-slate-200 max-w-2xl w-full p-6 shadow-xl space-y-4 max-h-[85vh] flex flex-col">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <div className="flex items-center space-x-2">
                    <FileText className="w-5 h-5 text-blue-600" />
                    <h3 className="text-base font-bold text-slate-900">
                      {docDetail?.title || "Document Details"}
                    </h3>
                  </div>
                  <button
                    onClick={() => {
                      setSelectedDocId(null);
                      setDocDetail(null);
                    }}
                    className="text-slate-400 hover:text-slate-600 p-1"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                {isLoadingDetail ? (
                  <div className="py-12 flex justify-center">
                    <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                  </div>
                ) : docDetail ? (
                  <div className="space-y-4 overflow-y-auto pr-1">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs font-mono">
                      <div>
                        <span className="text-slate-400 block text-[10px] uppercase">Format</span>
                        <span className="font-semibold text-slate-800">{docDetail.mime_type || "text/plain"}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px] uppercase">Size</span>
                        <span className="font-semibold text-slate-800">
                          {docDetail.file_size_bytes ? `${(docDetail.file_size_bytes / 1024).toFixed(1)} KB` : "N/A"}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px] uppercase">Pages</span>
                        <span className="font-semibold text-slate-800">{docDetail.page_count || 1}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px] uppercase">Chunks</span>
                        <span className="font-semibold text-slate-800">{docDetail.chunk_count}</span>
                      </div>
                    </div>

                    <div>
                      <span className="text-xs font-medium text-slate-700 block mb-1">SHA-256 Content Hash</span>
                      <p className="text-[11px] font-mono bg-slate-100 p-2 rounded border border-slate-200 break-all text-slate-600">
                        {docDetail.content_hash || "N/A"}
                      </p>
                    </div>

                    {docDetail.raw_content_preview && (
                      <div>
                        <span className="text-xs font-medium text-slate-700 block mb-1">Raw Content Preview</span>
                        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs font-sans text-slate-700 whitespace-pre-wrap max-h-48 overflow-y-auto">
                          {docDetail.raw_content_preview}
                        </div>
                      </div>
                    )}
                  </div>
                ) : null}

                <div className="flex justify-end pt-2 border-t border-slate-100">
                  <button
                    onClick={() => {
                      setSelectedDocId(null);
                      setDocDetail(null);
                    }}
                    className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-lg transition"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: GROUNDED DOCUMENT QUESTION ANSWERING */}
      {activeTab === "ask" && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-5 h-5 text-purple-600" />
                <h2 className="text-base font-bold text-slate-900">Document-Grounded Question Answering</h2>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200 font-mono">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                Hallucination-Protected QA
              </div>
            </div>

            <p className="text-xs text-slate-500">
              Ask questions directly against your uploaded documents or authoritative payment schemes. Answers are synthesized strictly from retrieved evidence with verifiable page and chunk citations.
            </p>

            {qaError && <ErrorAlert message={qaError} />}

            <form onSubmit={handleAskQuestion} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Knowledge Scope</label>
                  <select
                    value={qaScope}
                    onChange={(e: any) => setQaScope(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="uploaded">My Uploaded Documents Only</option>
                    <option value="knowledge_base">System Knowledge Base (Scheme Rules)</option>
                    <option value="all">Combined Knowledge (Uploaded + Scheme)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Target Document</label>
                  <select
                    value={qaTargetDocId}
                    onChange={(e) => setQaTargetDocId(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="all">All Documents in Selected Scope</option>
                    {documents.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.title} ({d.file_name || "file"})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="relative">
                <input
                  type="text"
                  required
                  placeholder="e.g. What is the mandatory settlement verification window under OVR-8841?"
                  value={qaQuery}
                  onChange={(e) => setQaQuery(e.target.value)}
                  className="w-full pl-10 pr-28 py-3 border border-slate-300 rounded-lg text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 shadow-2xs"
                />
                <HelpCircle className="w-5 h-5 text-slate-400 absolute left-3.5 top-3.5" />
                <button
                  type="submit"
                  disabled={isAsking || !qaQuery.trim()}
                  className="absolute right-2 top-2 px-4 py-1.5 bg-purple-600 hover:bg-purple-700 text-white font-medium text-xs rounded-md shadow-xs disabled:opacity-50 transition flex items-center gap-1.5"
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

          {/* QA Answer Response Card */}
          {qaResponse && (
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-100 gap-2">
                <div className="flex items-center space-x-2">
                  {qaResponse.is_grounded ? (
                    <div className="w-7 h-7 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700 shrink-0">
                      <CheckCircle2 className="w-4 h-4" />
                    </div>
                  ) : (
                    <div className="w-7 h-7 rounded-full bg-amber-100 flex items-center justify-center text-amber-700 shrink-0">
                      <AlertCircle className="w-4 h-4" />
                    </div>
                  )}
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">
                      {qaResponse.is_grounded ? "Evidence-Grounded Answer" : "Fact Absent / Abstention Notice"}
                    </h3>
                    <span className="text-[11px] font-mono text-slate-500">
                      Mode: {qaResponse.retrieval_mode_used} • Embeddings: {qaResponse.embedding_status}
                    </span>
                  </div>
                </div>

                <span className={`text-[11px] font-mono px-2.5 py-0.5 rounded-full border ${
                  qaResponse.is_grounded
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200 font-semibold"
                    : "bg-amber-50 text-amber-700 border-amber-200"
                }`}>
                  {qaResponse.is_grounded ? "VERIFIED GROUNDED" : "FACT NOT FOUND"}
                </span>
              </div>

              {/* Synthesized Answer */}
              <div className={`p-4 rounded-xl border text-sm leading-relaxed whitespace-pre-wrap ${
                qaResponse.is_grounded
                  ? "bg-purple-50/40 border-purple-200 text-slate-900"
                  : "bg-amber-50/50 border-amber-200 text-amber-900"
              }`}>
                {qaResponse.answer}
              </div>

              {/* Citations List */}
              {qaResponse.citations && qaResponse.citations.length > 0 && (
                <div className="space-y-3 pt-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5 text-slate-400" />
                    Source Provenance & Verifiable Citations ({qaResponse.citations.length})
                  </h4>

                  <div className="space-y-2">
                    {qaResponse.citations.map((cit, idx) => (
                      <div key={idx} className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-1.5">
                        <div className="flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-600 gap-2">
                          <span className="font-bold text-slate-900 flex items-center gap-1">
                            <FileText className="w-3.5 h-3.5 text-blue-600" />
                            {cit.document_name}
                          </span>
                          <span>Section: {cit.section}</span>
                          {cit.page && <span>Page #{cit.page}</span>}
                          <span className="text-slate-400 text-[10px]">Chunk: {cit.chunk_id.substring(0, 8)}...</span>
                        </div>
                        <p className="text-slate-700 italic border-l-2 border-purple-400 pl-2.5">
                          "{cit.excerpt}"
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: RULE EXPLORER (SEARCH) */}
      {activeTab === "search" && (
        <div className="space-y-6">
          {searchError && (
            <ErrorAlert
              message={searchError.message}
              code={searchError.code}
              retryAfter={searchError.retryAfter}
            />
          )}

          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs space-y-4">
            <form onSubmit={handleSearch} className="space-y-4">
              <div className="relative">
                <input
                  type="text"
                  required
                  placeholder="Query regulatory rules, dispute condition codes, or failure handling guidelines..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="w-full pl-10 pr-24 py-3 border border-slate-300 rounded-lg text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 shadow-2xs"
                />
                <Search className="w-5 h-5 text-slate-400 absolute left-3.5 top-3.5" />
                <button
                  type="submit"
                  disabled={isSearching || query.trim().length < 2}
                  className="absolute right-2 top-2 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-xs rounded-md shadow-xs disabled:opacity-50 transition flex items-center"
                >
                  {isSearching ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    "Search RAG"
                  )}
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Retrieval Engine</label>
                  <select
                    value={retrievalMode}
                    onChange={(e: any) => setRetrievalMode(e.target.value)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-md text-xs bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  >
                    <option value="hybrid">Hybrid (pgvector + FTS RRF)</option>
                    <option value="semantic_only">Semantic Only (pgvector Cosine)</option>
                    <option value="lexical_only">Lexical Only (PostgreSQL FTS)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Document Category</label>
                  <select
                    value={searchDocType}
                    onChange={(e) => setSearchDocType(e.target.value)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-md text-xs bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  >
                    <option value="">All Document Types</option>
                    <option value="scheme_rules">Scheme Rules (Visa, Mastercard, NACHA)</option>
                    <option value="refund_policy">Refund & Reversal Policies</option>
                    <option value="dispute_guide">Dispute Guidelines</option>
                    <option value="sla_spec">SLA & Settlement Specifications</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Top Candidates (K: {topK})</label>
                  <input
                    type="range"
                    min={1}
                    max={20}
                    value={topK}
                    onChange={(e) => setTopK(parseInt(e.target.value, 10))}
                    className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer mt-2"
                  />
                </div>
              </div>
            </form>
          </div>

          {/* Results Section */}
          {hasSearched && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>
                  Found <strong className="text-slate-900">{searchResults.length}</strong> ranked policy chunks{" "}
                  {totalCandidates !== null && `(evaluated ${totalCandidates} total candidates)`}
                </span>
                <span className="font-mono bg-slate-100 px-2 py-0.5 rounded text-slate-700">Mode: {retrievalMode}</span>
              </div>

              {searchResults.length === 0 ? (
                <EmptyState
                  title="No policy chunks matched"
                  description="Try broadening your search terms or changing the retrieval mode."
                />
              ) : (
                <div className="space-y-4">
                  {searchResults.map((item) => (
                    <div
                      key={item.chunk_id}
                      className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs space-y-3 hover:border-slate-300 transition"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-3 border-b border-slate-100 gap-2">
                        <div>
                          <div className="flex items-center space-x-2">
                            <FileText className="w-4 h-4 text-emerald-600" />
                            <h3 className="text-sm font-bold text-slate-900">{item.title}</h3>
                            <span className="text-[11px] font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                              {item.doc_type}
                            </span>
                          </div>
                          <span className="text-xs font-mono text-slate-500 mt-1 block">
                            {item.section_header} • Chunk #{item.chunk_index} ({item.token_count} tokens)
                          </span>
                        </div>

                        <div className="flex items-center space-x-2">
                          <div className="text-right">
                            <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-mono">
                              Fusion Score
                            </span>
                            <span className="text-sm font-mono font-bold text-slate-900">
                              {item.ranking.fusion_score.toFixed(4)}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-800 leading-relaxed font-sans whitespace-pre-wrap">
                        {item.content}
                      </div>

                      <div className="pt-2 flex flex-wrap items-center justify-between text-[11px] text-slate-500 font-mono gap-2">
                        <div className="flex space-x-4">
                          {item.ranking.semantic_similarity != null && (
                            <span>Cosine Similarity: {(item.ranking.semantic_similarity * 100).toFixed(1)}%</span>
                          )}
                          {item.ranking.lexical_rank != null && <span>FTS Rank: #{item.ranking.lexical_rank}</span>}
                          {item.ranking.semantic_rank != null && <span>Vector Rank: #{item.ranking.semantic_rank}</span>}
                        </div>

                        {item.source_url && (
                          <a
                            href={item.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-600 hover:underline flex items-center"
                          >
                            Source Document
                            <ExternalLink className="w-3 h-3 ml-1" />
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
