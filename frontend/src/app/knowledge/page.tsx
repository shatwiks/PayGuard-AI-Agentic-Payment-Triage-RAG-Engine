"use client";

import React, { useState } from "react";
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
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { SearchResultItem } from "@/lib/types";
import { ErrorAlert } from "@/components/ui/ErrorAlert";
import { EmptyState } from "@/components/ui/EmptyState";

export default function KnowledgeSearchPage() {
  const [query, setQuery] = useState("");
  const [retrievalMode, setRetrievalMode] = useState<"hybrid" | "semantic_only" | "lexical_only">("hybrid");
  const [docType, setDocType] = useState<string>("");
  const [topK, setTopK] = useState<number>(5);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [totalCandidates, setTotalCandidates] = useState<number | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<{ message: string; code?: string; retryAfter?: number | null } | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || query.trim().length < 2) return;

    setIsSearching(true);
    setError(null);
    setHasSearched(true);

    try {
      const response = await api.searchKnowledge({
        query: query.trim(),
        top_k: topK,
        retrieval_mode: retrievalMode,
        doc_type: docType || undefined,
      });
      setResults(response.results || []);
      setTotalCandidates(response.total_candidates);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError({
          message: err.message,
          code: err.code,
          retryAfter: err.retryAfter,
        });
      } else {
        setError({
          message: "Unable to complete knowledge search request.",
        });
      }
    } finally {
      setIsSearching(false);
    }
  };

  const sampleQueries = [
    "ACH return code R01 insufficient funds",
    "Visa Condition 10.4 fraud dispute timeline",
    "Instant payout settlement failure refund policy",
    "Duplicate charge merchant refund SLA",
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Payment Policy & Rule Explorer</h1>
        <p className="text-sm text-slate-500 mt-1">
          Search authoritative scheme rules, card network dispute guides, and internal SOP policies via pgvector RAG.
        </p>
      </div>

      {error && (
        <ErrorAlert
          message={error.message}
          code={error.code}
          retryAfter={error.retryAfter}
        />
      )}

      {/* Search Input Box & Controls */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs space-y-4">
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="relative">
            <input
              type="text"
              required
              placeholder="Query regulatory rules, dispute condition codes, or failure handling guidelines..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full pl-10 pr-24 py-3 border border-slate-300 rounded-lg text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-2xs"
            />
            <Search className="w-5 h-5 text-slate-400 absolute left-3.5 top-3.5" />
            <button
              type="submit"
              disabled={isSearching || query.trim().length < 2}
              className="absolute right-2 top-2 px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs rounded-md shadow-xs disabled:opacity-50 transition flex items-center"
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

          {/* Search Options / Filters */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Retrieval Engine
              </label>
              <select
                value={retrievalMode}
                onChange={(e: any) => setRetrievalMode(e.target.value)}
                className="w-full px-3 py-1.5 border border-slate-300 rounded-md text-xs bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="hybrid">Hybrid (pgvector + FTS RRF)</option>
                <option value="semantic_only">Semantic Only (pgvector Cosine)</option>
                <option value="lexical_only">Lexical Only (PostgreSQL FTS)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Document Category
              </label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                className="w-full px-3 py-1.5 border border-slate-300 rounded-md text-xs bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Document Types</option>
                <option value="scheme_rules">Scheme Rules (Visa, Mastercard, NACHA)</option>
                <option value="refund_policy">Refund & Reversal Policies</option>
                <option value="dispute_guide">Dispute Guidelines</option>
                <option value="sla_spec">SLA & Settlement Specifications</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Top Candidates (K: {topK})
              </label>
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

        {/* Query Suggestions */}
        {!hasSearched && (
          <div className="pt-2 border-t border-slate-100">
            <span className="text-xs text-slate-400 block mb-2">Try sample policy queries:</span>
            <div className="flex flex-wrap gap-2">
              {sampleQueries.map((sample, idx) => (
                <button
                  key={idx}
                  onClick={() => setQuery(sample)}
                  className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded-md transition"
                >
                  {sample}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Results Section */}
      {hasSearched && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>
              Found <strong className="text-slate-900">{results.length}</strong> ranked policy chunks{" "}
              {totalCandidates !== null && `(evaluated ${totalCandidates} total candidates)`}
            </span>
            <span className="font-mono bg-slate-100 px-2 py-0.5 rounded text-slate-700">
              Mode: {retrievalMode}
            </span>
          </div>

          {results.length === 0 ? (
            <EmptyState
              title="No policy chunks matched"
              description="Try broadening your search terms or changing the retrieval mode."
            />
          ) : (
            <div className="space-y-4">
              {results.map((item) => (
                <div
                  key={item.chunk_id}
                  className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs space-y-3 hover:border-slate-300 transition"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-3 border-b border-slate-100 gap-2">
                    <div>
                      <div className="flex items-center space-x-2">
                        <FileText className="w-4 h-4 text-purple-600" />
                        <h3 className="text-sm font-bold text-slate-900">{item.title}</h3>
                        <span className="text-[11px] font-mono text-purple-700 bg-purple-50 px-2 py-0.5 rounded border border-purple-200">
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

                  {/* Verbatim Content */}
                  <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-800 leading-relaxed font-sans whitespace-pre-wrap">
                    {item.content}
                  </div>

                  {/* Scoring Transparency Breakdown */}
                  <div className="pt-2 flex flex-wrap items-center justify-between text-[11px] text-slate-500 font-mono gap-2">
                    <div className="flex space-x-4">
                      {item.ranking.semantic_similarity != null && (
                        <span>
                          Cosine Similarity: {(item.ranking.semantic_similarity * 100).toFixed(1)}%
                        </span>
                      )}
                      {item.ranking.lexical_rank != null && (
                        <span>FTS Rank: #{item.ranking.lexical_rank}</span>
                      )}
                      {item.ranking.semantic_rank != null && (
                        <span>Vector Rank: #{item.ranking.semantic_rank}</span>
                      )}
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
  );
}
