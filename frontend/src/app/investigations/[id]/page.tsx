"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  BookOpen,
  Copy,
  Check,
  Clock,
  Layers,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Cpu,
  UserCheck,
  FileSearch,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { InvestigationCase, PolicyCitation } from "@/lib/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ErrorAlert } from "@/components/ui/ErrorAlert";
import { CardSkeleton } from "@/components/ui/LoadingSkeleton";

export default function InvestigationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const investigationId = resolvedParams.id;

  const [caseData, setCaseData] = useState<InvestigationCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code?: string; retryAfter?: number | null } | null>(null);
  const [copied, setCopied] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<PolicyCitation | null>(null);
  const [showEvidence, setShowEvidence] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .getInvestigation(investigationId)
      .then((data) => setCaseData(data))
      .catch((err: any) => {
        if (err instanceof ApiError) {
          setError({
            message: err.message,
            code: err.code,
            retryAfter: err.retryAfter,
          });
        } else {
          setError({
            message: "Unable to retrieve investigation case.",
          });
        }
      })
      .finally(() => setLoading(false));
  }, [investigationId]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-6 w-32 bg-slate-200 animate-pulse rounded" />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  if (error || !caseData) {
    return (
      <div className="space-y-4">
        <Link
          href="/investigations"
          className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-slate-800"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back to Investigations
        </Link>
        <ErrorAlert
          message={error?.message || "Investigation case not found or access unauthorized."}
          code={error?.code}
          retryAfter={error?.retryAfter}
        />
      </div>
    );
  }

  const result = caseData.result;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <Link
            href="/investigations"
            className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-slate-800 mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" />
            Back to Investigations
          </Link>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 font-mono">
              {caseData.case_number}
            </h1>
            <StatusBadge status={caseData.status} type="case" />
            <StatusBadge status={caseData.priority} type="priority" />
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Initiated on {new Date(caseData.created_at).toLocaleString()}
            {result?.execution_time_ms && (
              <span className="ml-2 font-mono text-slate-400">
                ({result.execution_time_ms}ms latency)
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => copyToClipboard(caseData.case_number)}
            className="inline-flex items-center px-3 py-2 border border-slate-300 rounded-lg text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 transition shadow-2xs"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-600 mr-1.5" />
                Copied Case #
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-slate-500 mr-1.5" />
                Copy Case #
              </>
            )}
          </button>
        </div>
      </div>

      {/* Human Review Alert Banner if Flagged */}
      {result?.human_review_required && (
        <div className="p-4 rounded-xl border border-amber-300 bg-amber-50 text-amber-950 flex items-start">
          <AlertTriangle className="w-5 h-5 text-amber-600 mr-3 mt-0.5 shrink-0" />
          <div>
            <h3 className="text-sm font-semibold">Human Review & Sign-Off Required</h3>
            <p className="text-xs text-amber-800 mt-0.5">
              {result.human_review_reason || "This investigation identified conflicting transaction records or regulatory thresholds requiring manual analyst approval."}
            </p>
          </div>
        </div>
      )}

      {/* Primary Triage Outcome Card */}
      {result ? (
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-slate-100 gap-4">
            <div>
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Deterministic Triage Classification
              </span>
              <h2 className="text-lg font-bold text-slate-900 capitalize mt-0.5">
                {result.issue_category.replace("_", " ")}
              </h2>
            </div>

            <div className="flex items-center space-x-6">
              <div>
                <span className="text-xs text-slate-500 block">Classification Confidence</span>
                <div className="flex items-center space-x-2 mt-1">
                  <div className="w-24 bg-slate-100 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-blue-600 h-2 rounded-full"
                      style={{ width: `${Math.round(result.confidence_score * 100)}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono font-semibold text-slate-800">
                    {Math.round(result.confidence_score * 100)}%
                  </span>
                </div>
              </div>

              {caseData.payment && (
                <div>
                  <span className="text-xs text-slate-500 block">Payment Reference</span>
                  <Link
                    href={`/payments/${caseData.payment.id}`}
                    className="text-xs font-mono font-semibold text-blue-600 hover:text-blue-800 flex items-center mt-1"
                  >
                    {caseData.payment.payment_reference}
                    <ExternalLink className="w-3 h-3 ml-1" />
                  </Link>
                </div>
              )}
            </div>
          </div>

          {/* Synthesized Grounded Explanation */}
          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Autonomous Root-Cause Synthesis
            </h3>
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 text-sm text-slate-800 leading-relaxed font-sans">
              {result.investigation_summary}
            </div>
          </div>

          {/* Recommended Operational Action */}
          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Prescribed Action & Next Steps
            </h3>
            <div className="p-4 rounded-lg bg-blue-50/70 border border-blue-200">
              <div className="flex items-center space-x-2 mb-2">
                <span className="px-2.5 py-1 rounded-md bg-blue-600 text-white font-mono text-xs font-bold uppercase tracking-wide">
                  {result.recommended_action}
                </span>
                <span className="text-xs font-medium text-blue-900">Recommended Resolution Action</span>
              </div>
              <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">
                {result.recommended_action_details}
              </p>
            </div>
          </div>

          {/* Missing or Conflicting Records */}
          {result.missing_or_conflicting_info && result.missing_or_conflicting_info.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Information Gaps & Telemetry Conflicts
              </h3>
              <ul className="space-y-1.5 pl-5 list-disc text-xs text-slate-700">
                {result.missing_or_conflicting_info.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {/* RAG Engine Metadata Footer */}
          <div className="pt-4 border-t border-slate-100 flex flex-wrap items-center justify-between text-[11px] text-slate-400 gap-2">
            <span className="flex items-center">
              <Cpu className="w-3.5 h-3.5 mr-1 text-slate-500" />
              Engine: {result.llm_model_name} ({result.generation_mode})
            </span>
            <span>Retrieval: {result.retrieval_mode} search</span>
            <span>Citations: {result.policy_citations.length} regulatory passages</span>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
          <Clock className="w-8 h-8 text-amber-500 mx-auto mb-2 animate-spin" />
          <h3 className="text-sm font-semibold text-slate-800">Investigation In Progress</h3>
          <p className="text-xs text-slate-500 mt-1">Autonomous triage pipeline is executing...</p>
        </div>
      )}

      {/* Grounded Policy Citations Section */}
      {result && result.policy_citations && result.policy_citations.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-900 flex items-center">
                <BookOpen className="w-4 h-4 mr-2 text-purple-600" />
                Grounded Policy Citations
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Official regulatory rules and internal SOP passages retrieved via pgvector RAG
              </p>
            </div>
            <span className="text-xs font-mono bg-purple-50 text-purple-700 border border-purple-200 px-2.5 py-0.5 rounded-full font-medium">
              {result.policy_citations.length} cited sources
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {result.policy_citations.map((citation, index) => (
              <div
                key={index}
                onClick={() => setSelectedCitation(citation)}
                className="cursor-pointer p-4 rounded-lg border border-slate-200 hover:border-purple-300 hover:bg-purple-50/20 transition flex flex-col justify-between space-y-3"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <span className="font-semibold text-xs text-slate-900 line-clamp-1">
                      {citation.document_title}
                    </span>
                    {citation.confidence_score != null && (
                      <span className="text-[11px] font-mono text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded">
                        Score: {citation.confidence_score.toFixed(3)}
                      </span>
                    )}
                  </div>
                  <span className="inline-block text-[11px] font-mono text-slate-500 mt-0.5">
                    {citation.section_header}
                  </span>
                  <p className="text-xs text-slate-600 mt-2 line-clamp-3 italic">
                    &ldquo;{citation.excerpt}&rdquo;
                  </p>
                </div>

                <div className="text-[11px] font-medium text-purple-600 flex items-center justify-end">
                  <span>Inspect verbatim passage &rarr;</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Customer Query Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
          Sanitized Customer Dispute Inquiry
        </h3>
        <p className="text-sm text-slate-800 bg-slate-50 p-4 rounded-lg border border-slate-200">
          {caseData.customer_query}
        </p>
      </div>

      {/* Verified Evidence Package (Collapsible) */}
      {result?.evidence_package && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs">
          <button
            onClick={() => setShowEvidence(!showEvidence)}
            className="w-full flex items-center justify-between text-left"
          >
            <div>
              <h3 className="text-sm font-semibold text-slate-900 flex items-center">
                <Layers className="w-4 h-4 mr-2 text-slate-500" />
                Verified Telemetry Evidence Package
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Audit trail snapshot of payment facts and gateway webhook state
              </p>
            </div>
            {showEvidence ? (
              <ChevronUp className="w-5 h-5 text-slate-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-slate-400" />
            )}
          </button>

          {showEvidence && (
            <pre className="mt-4 p-4 rounded-lg bg-slate-900 text-slate-200 font-mono text-xs overflow-x-auto max-h-96">
              {JSON.stringify(result.evidence_package, null, 2)}
            </pre>
          )}
        </div>
      )}

      {/* Citation Detail Modal / Drawer */}
      {selectedCitation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-2xs">
          <div className="bg-white rounded-xl max-w-xl w-full p-6 shadow-xl border border-slate-200 space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs text-purple-600 font-semibold uppercase tracking-wider">
                  Authoritative Grounding Source
                </span>
                <h3 className="text-lg font-bold text-slate-900 mt-1">
                  {selectedCitation.document_title}
                </h3>
                <span className="text-xs font-mono text-slate-500 block mt-0.5">
                  Section: {selectedCitation.section_header}
                </span>
              </div>
              <button
                onClick={() => setSelectedCitation(null)}
                className="text-slate-400 hover:text-slate-700 text-sm font-semibold p-1"
              >
                ✕
              </button>
            </div>

            <div className="p-4 bg-purple-50/40 rounded-lg border border-purple-200 text-sm text-slate-800 leading-relaxed font-sans whitespace-pre-wrap">
              &ldquo;{selectedCitation.excerpt}&rdquo;
            </div>

            <div className="space-y-1 text-xs text-slate-500 font-mono">
              {selectedCitation.source_id && <div>Source ID: {selectedCitation.source_id}</div>}
              {selectedCitation.source_url && (
                <div>
                  URL:{" "}
                  <a
                    href={selectedCitation.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    {selectedCitation.source_url}
                  </a>
                </div>
              )}
              {selectedCitation.confidence_score != null && (
                <div>Relevance Similarity Score: {selectedCitation.confidence_score.toFixed(4)}</div>
              )}
            </div>

            <div className="pt-3 border-t border-slate-100 flex justify-end">
              <button
                onClick={() => setSelectedCitation(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium transition"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
