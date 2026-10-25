"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import {
  ArrowLeft,
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
  CreditCard,
  Activity,
  Terminal,
  FileSearch,
  ShieldAlert,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { InvestigationCase, PaymentDetail, PolicyCitation } from "@/lib/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ErrorAlert } from "@/components/ui/ErrorAlert";
import { CardSkeleton } from "@/components/ui/LoadingSkeleton";
import { EvidenceDrawer } from "@/components/ui/EvidenceDrawer";
import { useToast } from "@/components/ui/ToastContext";

export default function InvestigationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const investigationId = resolvedParams.id;
  const { addToast } = useToast();

  const [caseData, setCaseData] = useState<InvestigationCase | null>(null);
  const [paymentDetail, setPaymentDetail] = useState<PaymentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{
    message: string;
    code?: string;
    retryAfter?: number | null;
  } | null>(null);
  const [copied, setCopied] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<PolicyCitation | null>(null);
  const [showEvidence, setShowEvidence] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    api
      .getInvestigation(investigationId)
      .then(async (data) => {
        if (!active) return;
        setCaseData(data);
        if (data.payment?.id) {
          try {
            const pDetail = await api.getPayment(data.payment.id);
            if (active) setPaymentDetail(pDetail);
          } catch {
            // Non-blocking if detailed payment timeline fetch fails
          }
        }
      })
      .catch((err: unknown) => {
        if (!active) return;
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
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [investigationId]);

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      addToast(`Copied ${text} to clipboard`, "success");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      addToast("Unable to copy to clipboard", "error");
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-6 w-36 bg-[#171C21] animate-pulse rounded" />
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
          className="inline-flex items-center text-xs font-medium text-[#9BA5B0] hover:text-[#F3F5F7] transition"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          Back to Investigations
        </Link>
        <ErrorAlert
          message={
            error?.message ||
            "Investigation case not found or access unauthorized."
          }
          code={error?.code}
          retryAfter={error?.retryAfter}
        />
      </div>
    );
  }

  const result = caseData.result;

  return (
    <div className="space-y-6">
      {/* Workspace Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#1F262E]">
        <div>
          <Link
            href="/investigations"
            className="inline-flex items-center text-xs font-medium text-[#9BA5B0] hover:text-[#F3F5F7] mb-2 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
            Back to Investigations
          </Link>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-[#F3F5F7] font-mono tabular-nums">
              {caseData.case_number}
            </h1>
            <StatusBadge status={caseData.status} type="case" />
            <StatusBadge status={caseData.priority} type="priority" />
            {result?.execution_time_ms != null && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#111519] border border-[#1F262E] text-[11px] font-mono text-[#9BA5B0] tabular-nums">
                <Clock className="w-3 h-3 text-[#C6F36A]" />
                {result.execution_time_ms}ms
              </span>
            )}
          </div>
          <p className="text-xs text-[#6E7A87] mt-1 font-mono tabular-nums">
            Initiated {new Date(caseData.created_at).toLocaleString()} • Case ID: {caseData.id}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {caseData.payment && (
            <Link
              href={`/payments/${caseData.payment.id}`}
              className="inline-flex items-center px-3 py-2 border border-[#262F38] rounded-xl text-xs font-medium text-[#9BA5B0] bg-[#111519] hover:text-[#F3F5F7] hover:border-[#384654] transition"
            >
              <CreditCard className="w-3.5 h-3.5 mr-1.5 text-[#C6F36A]" />
              <span className="font-mono">{caseData.payment.payment_reference}</span>
              <ExternalLink className="w-3 h-3 ml-1.5" />
            </Link>
          )}
          <button
            type="button"
            onClick={() => copyToClipboard(caseData.case_number)}
            className="inline-flex items-center px-3.5 py-2 border border-[#262F38] rounded-xl text-xs font-medium text-[#F3F5F7] bg-[#111519] hover:bg-[#171C21] hover:border-[#384654] transition active:scale-[0.98]"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-[#2DD4BF] mr-1.5" />
                Copied Case #
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-[#9BA5B0] mr-1.5" />
                Copy Case #
              </>
            )}
          </button>
        </div>
      </div>

      {/* Human Review Alert Banner if Flagged */}
      {result?.human_review_required && (
        <div
          role="region"
          aria-label="Human review required"
          className="p-4 rounded-xl border border-[#F59E0B]/40 bg-[#F59E0B]/10 text-[#F3F5F7] flex items-start gap-3"
        >
          <AlertTriangle className="w-5 h-5 text-[#F59E0B] mt-0.5 shrink-0" />
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#F59E0B]">
              Human Review & Analyst Sign-Off Required
            </h2>
            <p className="text-xs text-[#9BA5B0] mt-1 leading-relaxed">
              {result.human_review_reason ||
                "This investigation identified conflicting transaction records or regulatory thresholds requiring manual analyst approval before settlement execution."}
            </p>
          </div>
        </div>
      )}

      {/* 3-Column Financial Investigation Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT COLUMN (4 cols): Payment Context, Customer Inquiry & Event Timeline */}
        <div className="lg:col-span-4 space-y-6">
          {/* Customer Dispute Inquiry */}
          <div className="pg-surface-shell">
            <div className="pg-surface-core p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono uppercase tracking-wider text-[#9BA5B0]">
                  Sanitized Customer Dispute Inquiry
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#171C21] border border-[#262F38] text-[#9BA5B0]">
                  Input Context
                </span>
              </div>
              <p className="text-xs text-[#F3F5F7] bg-[#0B0D0F] p-3.5 rounded-xl border border-[#1F262E] leading-relaxed">
                {caseData.customer_query}
              </p>
            </div>
          </div>

          {/* Linked Payment Telemetry Card */}
          <div className="pg-surface-shell">
            <div className="pg-surface-core p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-[#1F262E] pb-3">
                <div className="flex items-center gap-2">
                  <CreditCard className="w-4 h-4 text-[#C6F36A]" />
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-[#F3F5F7]">
                    Confirmed Payment Telemetry
                  </h2>
                </div>
                {caseData.payment && (
                  <StatusBadge status={caseData.payment.status} type="payment" />
                )}
              </div>

              {caseData.payment ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="p-3 rounded-xl bg-[#0B0D0F] border border-[#1F262E]">
                      <span className="text-[10px] font-mono uppercase text-[#6E7A87] block">
                        Reference
                      </span>
                      <Link
                        href={`/payments/${caseData.payment.id}`}
                        className="font-mono font-semibold text-[#C6F36A] hover:underline mt-0.5 inline-flex items-center gap-1"
                      >
                        {caseData.payment.payment_reference}
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    </div>
                    <div className="p-3 rounded-xl bg-[#0B0D0F] border border-[#1F262E]">
                      <span className="text-[10px] font-mono uppercase text-[#6E7A87] block">
                        Amount
                      </span>
                      <span className="font-mono font-bold text-[#F3F5F7] tabular-nums mt-0.5 block">
                        {caseData.payment.currency}{" "}
                        {Number(caseData.payment.amount).toFixed(2)}
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-[#0B0D0F] border border-[#1F262E]">
                      <span className="text-[10px] font-mono uppercase text-[#6E7A87] block">
                        Payment Rail
                      </span>
                      <span className="font-medium text-[#F3F5F7] capitalize mt-0.5 block">
                        {caseData.payment.payment_method.replace("_", " ")}
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-[#0B0D0F] border border-[#1F262E]">
                      <span className="text-[10px] font-mono uppercase text-[#6E7A87] block">
                        Gateway
                      </span>
                      <span className="font-medium text-[#F3F5F7] capitalize mt-0.5 block">
                        {caseData.payment.gateway_name}
                      </span>
                    </div>
                  </div>

                  {paymentDetail &&
                    (paymentDetail.failure_code || paymentDetail.failure_message) && (
                      <div className="p-3 rounded-xl bg-[#F87171]/10 border border-[#F87171]/30 text-xs">
                        <span className="font-mono font-semibold text-[#F87171] block">
                          Gateway Failure: {paymentDetail.failure_code || "REJECTED"}
                        </span>
                        {paymentDetail.failure_message && (
                          <p className="text-[#9BA5B0] mt-1">
                            {paymentDetail.failure_message}
                          </p>
                        )}
                      </div>
                    )}

                  {/* Chronological Event Timeline */}
                  {paymentDetail && paymentDetail.events.length > 0 && (
                    <div className="pt-2 border-t border-[#1F262E] space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-mono uppercase tracking-wider text-[#9BA5B0]">
                          State Transition Timeline
                        </span>
                        <span className="text-[11px] font-mono text-[#6E7A87] tabular-nums">
                          {paymentDetail.events.length} events
                        </span>
                      </div>
                      <div className="relative pl-4 space-y-3 before:absolute before:left-1.5 before:top-1.5 before:bottom-1.5 before:w-px before:bg-[#262F38]">
                        {paymentDetail.events.map((evt) => (
                          <div key={evt.id} className="relative">
                            <span className="absolute -left-4 top-1.5 w-2 h-2 rounded-full bg-[#C6F36A]" />
                            <div className="p-2.5 rounded-lg bg-[#0B0D0F] border border-[#1F262E] text-xs">
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-mono font-semibold text-[#F3F5F7]">
                                  {evt.event_type}
                                </span>
                                <span className="text-[10px] font-mono text-[#6E7A87] tabular-nums">
                                  {new Date(evt.occurred_at).toLocaleTimeString([], {
                                    hour: "2-digit",
                                    minute: "2-digit",
                                    second: "2-digit",
                                  })}
                                </span>
                              </div>
                              <div className="text-[11px] font-mono text-[#9BA5B0] mt-1">
                                {evt.from_status ? `${evt.from_status} → ` : ""}
                                <span className="text-[#C6F36A]">{evt.to_status}</span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-[#0B0D0F] border border-[#1F262E] text-xs text-[#9BA5B0] space-y-1.5">
                  <p className="font-semibold text-[#F3F5F7]">
                    No Payment Record Linked
                  </p>
                  <p className="leading-relaxed">
                    This investigation was initiated from a natural-language customer inquiry without a verified transaction identifier.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* CENTER COLUMN (5 cols): Triage Classification, Root-Cause Synthesis & Prescribed Action */}
        <div className="lg:col-span-5 space-y-6">
          {result ? (
            <div className="pg-surface-shell">
              <div className="pg-surface-core p-6 space-y-6">
                {/* Classification Header */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-[#1F262E] gap-4">
                  <div>
                    <span className="text-[11px] font-mono text-[#9BA5B0] uppercase tracking-wider block">
                      Deterministic Triage Classification
                    </span>
                    <div className="flex items-center gap-2.5 mt-1">
                      <h2 className="text-lg font-bold text-[#F3F5F7] capitalize">
                        {result.issue_category.replace("_", " ")}
                      </h2>
                      <span className="px-2 py-0.5 rounded bg-[#171C21] border border-[#262F38] font-mono text-[11px] text-[#C6F36A]">
                        {result.issue_category}
                      </span>
                    </div>
                  </div>

                  <div className="sm:text-right">
                    <span className="text-[11px] font-mono text-[#9BA5B0] uppercase tracking-wider block">
                      Confidence Score
                    </span>
                    <div className="flex items-center sm:justify-end space-x-2.5 mt-1.5">
                      <div className="w-24 bg-[#0B0D0F] border border-[#262F38] rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-[#C6F36A] h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${Math.round(result.confidence_score * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="text-xs font-mono font-bold text-[#F3F5F7] tabular-nums">
                        {Math.round(result.confidence_score * 100)}%
                      </span>
                    </div>
                  </div>
                </div>

                {/* Synthesized Grounded Explanation */}
                <div>
                  <h3 className="text-[11px] font-mono font-semibold text-[#9BA5B0] uppercase tracking-wider mb-2">
                    Autonomous Root-Cause Synthesis
                  </h3>
                  <div className="p-4 rounded-xl bg-[#0B0D0F] border border-[#1F262E] text-sm text-[#F3F5F7] leading-relaxed">
                    {result.investigation_summary}
                  </div>
                </div>

                {/* Prescribed Action */}
                <div>
                  <h3 className="text-[11px] font-mono font-semibold text-[#9BA5B0] uppercase tracking-wider mb-2">
                    Prescribed Action & Next Steps
                  </h3>
                  <div className="p-4 rounded-xl bg-[#C6F36A]/5 border border-[#C6F36A]/30 space-y-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="px-2.5 py-1 rounded-md bg-[#C6F36A] text-[#0B0D0F] font-mono text-xs font-bold uppercase tracking-wide">
                        {result.recommended_action}
                      </span>
                      <span className="text-xs font-medium text-[#F3F5F7]">
                        Recommended Resolution Protocol
                      </span>
                    </div>
                    <p className="text-xs text-[#9BA5B0] leading-relaxed whitespace-pre-line">
                      {result.recommended_action_details}
                    </p>
                  </div>
                </div>

                {/* Missing or Conflicting Records */}
                {result.missing_or_conflicting_info &&
                  result.missing_or_conflicting_info.length > 0 && (
                    <div>
                      <h3 className="text-[11px] font-mono font-semibold text-[#F59E0B] uppercase tracking-wider mb-2">
                        Information Gaps & Telemetry Conflicts
                      </h3>
                      <ul className="space-y-1.5 p-3.5 rounded-xl bg-[#F59E0B]/5 border border-[#F59E0B]/25 text-xs text-[#F3F5F7]">
                        {result.missing_or_conflicting_info.map((item, idx) => (
                          <li key={idx} className="flex items-start gap-2">
                            <span className="text-[#F59E0B] font-mono">•</span>
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                {/* RAG Engine Metadata Footer */}
                <div className="pt-4 border-t border-[#1F262E] flex flex-wrap items-center justify-between text-[11px] font-mono text-[#6E7A87] gap-2">
                  <span className="flex items-center text-[#9BA5B0]">
                    <Cpu className="w-3.5 h-3.5 mr-1.5 text-[#C6F36A]" />
                    Engine: {result.llm_model_name} ({result.generation_mode})
                  </span>
                  <span>Retrieval: {result.retrieval_mode}</span>
                  <span>Citations: {result.policy_citations.length}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="pg-surface-shell">
              <div className="pg-surface-core p-8 text-center">
                <Clock className="w-8 h-8 text-[#F59E0B] mx-auto mb-2 animate-spin" />
                <h3 className="text-sm font-semibold text-[#F3F5F7]">
                  Investigation In Progress
                </h3>
                <p className="text-xs text-[#9BA5B0] mt-1">
                  Autonomous triage pipeline is executing...
                </p>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT COLUMN (3 cols): Grounded Policy Citations & Audit Telemetry Inspector */}
        <div className="lg:col-span-3 space-y-6">
          <div className="pg-surface-shell">
            <div className="pg-surface-core p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-[#1F262E] pb-3">
                <div className="flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-[#C6F36A]" />
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-[#F3F5F7]">
                    Grounded Policy Citations
                  </h2>
                </div>
                <span className="text-[11px] font-mono bg-[#171C21] text-[#C6F36A] border border-[#262F38] px-2 py-0.5 rounded-md tabular-nums">
                  {result?.policy_citations?.length || 0}
                </span>
              </div>

              {result &&
              result.policy_citations &&
              result.policy_citations.length > 0 ? (
                <div className="space-y-3">
                  {result.policy_citations.map((citation, index) => (
                    <button
                      type="button"
                      key={index}
                      onClick={() => setSelectedCitation(citation)}
                      className="w-full text-left p-3.5 rounded-xl bg-[#0B0D0F] border border-[#1F262E] hover:border-[#C6F36A]/50 hover:bg-[#171C21]/60 transition flex flex-col justify-between space-y-2.5 group"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <span className="font-semibold text-xs text-[#F3F5F7] group-hover:text-[#C6F36A] transition line-clamp-1">
                            {citation.document_title}
                          </span>
                          {citation.confidence_score != null && (
                            <span className="text-[10px] font-mono text-[#2DD4BF] bg-[#2DD4BF]/10 border border-[#2DD4BF]/25 px-1.5 py-0.5 rounded shrink-0 tabular-nums">
                              {citation.confidence_score.toFixed(3)}
                            </span>
                          )}
                        </div>
                        <span className="inline-block text-[11px] font-mono text-[#9BA5B0] mt-0.5">
                          {citation.section_header}
                        </span>
                        <p className="text-xs text-[#9BA5B0] mt-2 line-clamp-3 italic border-l-2 border-[#C6F36A]/40 pl-2.5">
                          &ldquo;{citation.excerpt}&rdquo;
                        </p>
                      </div>

                      <div className="text-[11px] font-mono text-[#C6F36A] flex items-center justify-end">
                        <span>Inspect verbatim passage &rarr;</span>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-[#0B0D0F] border border-[#1F262E] text-xs text-[#9BA5B0]">
                  No regulatory passages were cited for this triage case.
                </div>
              )}
            </div>
          </div>

          {/* Verified Audit & Telemetry Evidence Package */}
          {result?.evidence_package && (
            <div className="pg-surface-shell">
              <div className="pg-surface-core p-5">
                <button
                  type="button"
                  onClick={() => setShowEvidence(!showEvidence)}
                  aria-expanded={showEvidence}
                  className="w-full flex items-center justify-between text-left"
                >
                  <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-[#C6F36A]" />
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-[#F3F5F7]">
                        Audit & Evidence Snapshot
                      </h3>
                      <p className="text-[11px] text-[#6E7A87] mt-0.5">
                        Deterministic state & retrieval trace
                      </p>
                    </div>
                  </div>
                  {showEvidence ? (
                    <ChevronUp className="w-4 h-4 text-[#9BA5B0]" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-[#9BA5B0]" />
                  )}
                </button>

                {showEvidence && (
                  <pre className="mt-4 p-3.5 rounded-xl bg-[#0B0D0F] border border-[#1F262E] text-[#9BA5B0] font-mono text-[11px] overflow-x-auto max-h-80">
                    {JSON.stringify(result.evidence_package, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Slide-Over Citation & Evidence Drawer */}
      <EvidenceDrawer
        isOpen={selectedCitation !== null}
        onClose={() => setSelectedCitation(null)}
        evidence={
          selectedCitation
            ? {
                title: selectedCitation.document_title,
                section: selectedCitation.section_header,
                excerpt: selectedCitation.excerpt,
                score: selectedCitation.confidence_score,
                scoreLabel: "Relevance Score",
                sourceId: selectedCitation.source_id,
                sourceUrl: selectedCitation.source_url,
              }
            : null
        }
      />
    </div>
  );
}
