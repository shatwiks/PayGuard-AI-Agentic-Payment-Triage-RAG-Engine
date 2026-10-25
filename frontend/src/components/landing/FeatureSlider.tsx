"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Clock,
  Cpu,
  FileCheck,
  GitCommit,
  Layers,
  Pause,
  Play,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { useReducedMotion } from "@/components/motion/MotionSystem";

interface SlideItem {
  id: string;
  indexLabel: string;
  title: string;
  subtitle: string;
  description: string;
  capabilities: string[];
  codeRef: string;
}

const SLIDES: SlideItem[] = [
  {
    id: "payment-investigation",
    indexLabel: "01",
    title: "Payment Investigation",
    subtitle: "Multi-rail transaction lookup & gateway error correlation",
    description:
      "Locate payment records by reference code, UUID, customer ID, or processor gateway. Inspect normalized status alongside raw processor failure codes without leaving the investigation console.",
    capabilities: [
      "Supports credit_card, debit_card, ach, and upi rails",
      "Instant reference verification before triage submission",
      "Direct correlation of gateway failure codes and timestamps",
    ],
    codeRef: "GET /api/v1/payments/by-reference/{reference}",
  },
  {
    id: "intelligent-triage",
    indexLabel: "02",
    title: "Intelligent Triage",
    subtitle: "Deterministic classification before generative synthesis",
    description:
      "PayGuard AI does not guess transaction states with an LLM. A deterministic rules engine evaluates payment status transitions, gateway error codes, and sanitized dispute text first.",
    capabilities: [
      "Deterministic category assignment & confidence scoring",
      "Automatic human-review escalation flags for high-risk cases",
      "Prescribed operational action codes (VOID_HOLD, REFUND, ESCALATE)",
    ],
    codeRef: "TriageRulesEngine.evaluate()",
  },
  {
    id: "evidence-grounded-rag",
    indexLabel: "03",
    title: "Evidence-Grounded RAG",
    subtitle: "Reciprocal Rank Fusion over pgvector & PostgreSQL FTS",
    description:
      "Combines 1536-dimension vector similarity with PostgreSQL full-text lexical ranking. A dedicated grounding verifier checks rule IDs, subjects, and numeric constraints before returning an answer.",
    capabilities: [
      "Hybrid RRF, Semantic-Only, and Lexical-Only retrieval modes",
      "Rule-ID specificity guard prevents cross-clause false positives",
      "Safe abstention when retrieved passages lack supporting facts",
    ],
    codeRef: "POST /api/v1/knowledge/ask • GroundingVerifier",
  },
  {
    id: "investigation-timeline",
    indexLabel: "04",
    title: "Investigation Timeline",
    subtitle: "Chronological webhook state transitions & payload inspection",
    description:
      "Reconstruct the exact sequence of authorization, capture, timeout, reversal, or dispute events. Expand individual processor webhooks to inspect raw JSON payloads in place.",
    capabilities: [
      "Ordered state transition graph (from_status → to_status)",
      "Expandable raw processor webhook JSON inspector",
      "Millisecond execution latency tracking per triage run",
    ],
    codeRef: "GET /api/v1/payments/{payment_id}",
  },
  {
    id: "audit-traceability",
    indexLabel: "05",
    title: "Audit and Traceability",
    subtitle: "Immutable evidence packages & tenant-isolated provenance",
    description:
      "Every completed investigation persists a snapshot of the sanitized query, retrieved policy citations, model metadata, and payment telemetry—scoped to the operator's role and tenant boundary.",
    capabilities: [
      "SHA-256 content hashing on all uploaded policy documents",
      "Role-based access control (support_agent, compliance_analyst, admin)",
      "Full telemetry evidence package preserved per case record",
    ],
    codeRef: "GET /api/v1/investigations/{investigation_id}",
  },
];

export function FeatureSlider() {
  const reducedMotion = useReducedMotion();
  const [activeIndex, setActiveIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [autoPlayEnabled, setAutoPlayEnabled] = useState(false);
  const touchStartX = useRef<number | null>(null);
  const touchEndX = useRef<number | null>(null);

  const totalSlides = SLIDES.length;

  const goToSlide = useCallback(
    (index: number) => {
      const normalized = ((index % totalSlides) + totalSlides) % totalSlides;
      setActiveIndex(normalized);
    },
    [totalSlides]
  );

  const handleNext = useCallback(() => {
    goToSlide(activeIndex + 1);
  }, [activeIndex, goToSlide]);

  const handlePrev = useCallback(() => {
    goToSlide(activeIndex - 1);
  }, [activeIndex, goToSlide]);

  // Optional user-toggled slow autoplay (disabled by default and disabled under reduced-motion)
  useEffect(() => {
    if (reducedMotion || !autoPlayEnabled || isPaused) return;
    const timer = setInterval(() => {
      handleNext();
    }, 7500);
    return () => clearInterval(timer);
  }, [reducedMotion, autoPlayEnabled, isPaused, handleNext]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      handleNext();
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      handlePrev();
    } else if (event.key === "Home") {
      event.preventDefault();
      goToSlide(0);
    } else if (event.key === "End") {
      event.preventDefault();
      goToSlide(totalSlides - 1);
    }
  };

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.changedTouches[0].clientX;
    touchEndX.current = null;
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    touchEndX.current = e.changedTouches[0].clientX;
  };

  const handleTouchEnd = () => {
    if (touchStartX.current === null || touchEndX.current === null) return;
    const deltaX = touchStartX.current - touchEndX.current;
    if (Math.abs(deltaX) > 45) {
      if (deltaX > 0) {
        handleNext();
      } else {
        handlePrev();
      }
    }
    touchStartX.current = null;
    touchEndX.current = null;
  };

  const activeSlide = SLIDES[activeIndex];

  return (
    <div
      className="rounded-2xl border border-[#1F262E] bg-[#111519] overflow-hidden shadow-[0_24px_64px_-16px_rgba(0,0,0,0.8)]"
      role="region"
      aria-roledescription="carousel"
      aria-label="PayGuard AI core architecture capabilities"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      onFocus={() => setIsPaused(true)}
      onBlur={() => setIsPaused(false)}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Top Bar: Slide Selector Tabs & Controls */}
      <div className="border-b border-[#1F262E] bg-[#0B0D0F]/70 px-4 sm:px-6 py-3.5 flex flex-wrap items-center justify-between gap-3">
        <div
          className="flex items-center gap-1.5 overflow-x-auto py-1"
          role="tablist"
          aria-label="Capability slides"
        >
          {SLIDES.map((slide, idx) => {
            const isSelected = idx === activeIndex;
            return (
              <button
                key={slide.id}
                type="button"
                role="tab"
                aria-selected={isSelected}
                aria-controls={`slide-panel-${slide.id}`}
                id={`slide-tab-${slide.id}`}
                onClick={() => goToSlide(idx)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition whitespace-nowrap flex items-center gap-2 ${
                  isSelected
                    ? "bg-[#171C21] text-[#C6F36A] border border-[#C6F36A]/35"
                    : "text-[#9BA5B0] hover:text-[#F3F5F7] hover:bg-[#171C21]/50 border border-transparent"
                }`}
              >
                <span className="font-mono text-[10px] opacity-75">
                  {slide.indexLabel}
                </span>
                <span>{slide.title}</span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 ml-auto">
          {!reducedMotion && (
            <button
              type="button"
              onClick={() => setAutoPlayEnabled((prev) => !prev)}
              aria-label={
                autoPlayEnabled ? "Pause slide rotation" : "Auto-advance slides"
              }
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-[#262F38] bg-[#171C21] hover:bg-[#1D242B] text-[11px] font-mono text-[#9BA5B0] hover:text-[#F3F5F7] transition"
            >
              {autoPlayEnabled ? (
                <>
                  <Pause className="w-3 h-3 text-[#C6F36A]" />
                  <span>Auto</span>
                </>
              ) : (
                <>
                  <Play className="w-3 h-3" />
                  <span>Manual</span>
                </>
              )}
            </button>
          )}

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={handlePrev}
              aria-label="Previous capability slide"
              className="p-2 rounded-lg border border-[#262F38] bg-[#171C21] hover:bg-[#1D242B] text-[#F3F5F7] transition active:scale-[0.97]"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={handleNext}
              aria-label="Next capability slide"
              className="p-2 rounded-lg border border-[#262F38] bg-[#171C21] hover:bg-[#1D242B] text-[#F3F5F7] transition active:scale-[0.97]"
            >
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Active Progress Bar */}
      <div className="w-full h-0.5 bg-[#171C21]">
        <div
          className="h-full bg-[#C6F36A] transition-all duration-300"
          style={{ width: `${((activeIndex + 1) / totalSlides) * 100}%` }}
        />
      </div>

      {/* Main Slide Body */}
      <div
        id={`slide-panel-${activeSlide.id}`}
        role="tabpanel"
        aria-labelledby={`slide-tab-${activeSlide.id}`}
        aria-live="polite"
        className="p-6 sm:p-8 lg:p-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center"
      >
        {/* Left Column: Slide Copy & Technical Details */}
        <div className="lg:col-span-5 space-y-5">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-[#171C21] border border-[#262F38] text-[11px] font-mono text-[#C6F36A]">
            <span>STAGE {activeSlide.indexLabel} / 05</span>
            <span className="text-[#6E7A87]">•</span>
            <span className="text-[#9BA5B0]">{activeSlide.codeRef}</span>
          </div>

          <div className="space-y-2">
            <h3 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#F3F5F7]">
              {activeSlide.title}
            </h3>
            <p className="text-sm font-medium text-[#C6F36A]/90">
              {activeSlide.subtitle}
            </p>
          </div>

          <p className="text-sm text-[#9BA5B0] leading-relaxed">
            {activeSlide.description}
          </p>

          <ul className="space-y-2.5 pt-2">
            {activeSlide.capabilities.map((cap, i) => (
              <li
                key={i}
                className="flex items-start gap-2.5 text-xs text-[#F3F5F7]/90"
              >
                <CheckCircle2 className="w-4 h-4 text-[#2DD4BF] shrink-0 mt-0.5" />
                <span>{cap}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Right Column: Distinct Visual Composition per Slide */}
        <div className="lg:col-span-7">
          {activeIndex === 0 && (
            /* Slide 1 Visual: Multi-Rail Transaction Lookup Schematic */
            <div className="rounded-xl border border-[#262F38] bg-[#0B0D0F] p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-[#1F262E] pb-3">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-[#C6F36A]" />
                  <span className="text-xs font-mono font-semibold text-[#F3F5F7]">
                    Payment Telemetry Lookup (Illustrative Sample)
                  </span>
                </div>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#2DD4BF]/10 text-[#2DD4BF] border border-[#2DD4BF]/25">
                  200 OK
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
                <div className="p-3 rounded-lg bg-[#111519] border border-[#1F262E]">
                  <span className="text-[10px] text-[#6E7A87] block">REFERENCE</span>
                  <span className="text-[#F3F5F7] font-semibold mt-0.5 block tabular-nums">
                    tx_20261020_0001
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-[#111519] border border-[#1F262E]">
                  <span className="text-[10px] text-[#6E7A87] block">AMOUNT</span>
                  <span className="text-[#C6F36A] font-semibold mt-0.5 block tabular-nums">
                    USD 149.99
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-[#111519] border border-[#1F262E]">
                  <span className="text-[10px] text-[#6E7A87] block">PAYMENT RAIL</span>
                  <span className="text-[#F3F5F7] mt-0.5 block">credit_card</span>
                </div>
                <div className="p-3 rounded-lg bg-[#111519] border border-[#1F262E]">
                  <span className="text-[10px] text-[#6E7A87] block">GATEWAY</span>
                  <span className="text-[#F3F5F7] mt-0.5 block">stripe_v3</span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-[#F87171]/10 border border-[#F87171]/30 flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <span className="text-[11px] font-mono font-semibold text-[#F87171] block">
                    GATEWAY_FAILURE_CODE: card_declined_51
                  </span>
                  <p className="text-xs text-[#F3F5F7]/90">
                    Processor reported insufficient funds on second capture attempt after initial authorization hold.
                  </p>
                </div>
                <span className="text-[11px] font-mono text-[#F59E0B] bg-[#F59E0B]/10 border border-[#F59E0B]/25 px-2 py-0.5 rounded shrink-0">
                  AUTHORIZED_HOLD
                </span>
              </div>
            </div>
          )}

          {activeIndex === 1 && (
            /* Slide 2 Visual: Deterministic Triage Classification Matrix */
            <div className="rounded-xl border border-[#262F38] bg-[#0B0D0F] p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-[#1F262E] pb-3">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-[#C6F36A]" />
                  <span className="text-xs font-mono font-semibold text-[#F3F5F7]">
                    Deterministic Triage Evaluation Matrix
                  </span>
                </div>
                <span className="text-[11px] font-mono text-[#9BA5B0]">
                  Rule Engine v1
                </span>
              </div>

              <div className="space-y-2.5">
                {[
                  {
                    signal: "Payment State & Hold Check",
                    detail: "status == 'authorized' && capture_ts == null",
                    weight: "+0.45",
                    matched: true,
                  },
                  {
                    signal: "Customer Dispute Pattern",
                    detail: "tokens: ['charged twice', 'duplicate', 'pending hold']",
                    weight: "+0.35",
                    matched: true,
                  },
                  {
                    signal: "Gateway Retry Telemetry",
                    detail: "2 authorization events within 60-second window",
                    weight: "+0.14",
                    matched: true,
                  },
                ].map((row, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-[#111519] border border-[#1F262E] flex items-center justify-between gap-3"
                  >
                    <div>
                      <span className="text-xs font-semibold text-[#F3F5F7] block">
                        {row.signal}
                      </span>
                      <span className="text-[11px] font-mono text-[#9BA5B0]">
                        {row.detail}
                      </span>
                    </div>
                    <span className="text-xs font-mono font-semibold text-[#C6F36A] bg-[#C6F36A]/10 border border-[#C6F36A]/30 px-2.5 py-1 rounded tabular-nums">
                      {row.weight}
                    </span>
                  </div>
                ))}
              </div>

              <div className="p-3.5 rounded-lg bg-[#171C21] border border-[#262F38] flex flex-wrap items-center justify-between gap-3">
                <div>
                  <span className="text-[10px] font-mono text-[#6E7A87] uppercase block">
                    Assigned Classification
                  </span>
                  <span className="text-sm font-mono font-bold text-[#F3F5F7]">
                    authorization_holds • Action: VOID_DUPLICATE_HOLD
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] font-mono text-[#6E7A87] uppercase block">
                    Confidence
                  </span>
                  <span className="text-sm font-mono font-bold text-[#2DD4BF] tabular-nums">
                    94.0%
                  </span>
                </div>
              </div>
            </div>
          )}

          {activeIndex === 2 && (
            /* Slide 3 Visual: Hybrid RRF Retrieval & Specificity Verifier */
            <div className="rounded-xl border border-[#262F38] bg-[#0B0D0F] p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-[#1F262E] pb-3">
                <div className="flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-[#C6F36A]" />
                  <span className="text-xs font-mono font-semibold text-[#F3F5F7]">
                    Hybrid RRF + Grounding Specificity Guard
                  </span>
                </div>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#C6F36A]/10 text-[#C6F36A] border border-[#C6F36A]/30">
                  pgvector + FTS
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="p-3.5 rounded-lg bg-[#111519] border border-[#2DD4BF]/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-mono font-semibold text-[#2DD4BF]">
                      VALID RULE QUERY
                    </span>
                    <span className="text-[10px] font-mono text-[#9BA5B0] tabular-nums">
                      RRF: 0.0328
                    </span>
                  </div>
                  <p className="text-xs font-mono text-[#F3F5F7]">
                    &ldquo;What does rule VP-SEPA-401 prohibit?&rdquo;
                  </p>
                  <p className="text-[11px] text-[#9BA5B0] border-l-2 border-[#2DD4BF] pl-2">
                    Grounded: &ldquo;Partial indemnity release is prohibited under rule VP-SEPA-401.&rdquo;
                  </p>
                </div>

                <div className="p-3.5 rounded-lg bg-[#111519] border border-[#F59E0B]/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-mono font-semibold text-[#F59E0B]">
                      UNSUPPORTED SUBJECT
                    </span>
                    <span className="text-[10px] font-mono text-[#F59E0B]">
                      ABSTAINED
                    </span>
                  </div>
                  <p className="text-xs font-mono text-[#F3F5F7]">
                    &ldquo;Paper check clearing under VP-SEPA-401?&rdquo;
                  </p>
                  <p className="text-[11px] text-[#9BA5B0] border-l-2 border-[#F59E0B] pl-2">
                    Refused: Rule ID matched, but subject &lsquo;paper check clearing&rsquo; is absent from evidence.
                  </p>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-[#171C21] border border-[#262F38] flex items-center justify-between text-xs font-mono text-[#9BA5B0]">
                <span>Embedding Model: nomic-embed-text (1536d)</span>
                <span className="text-[#2DD4BF]">Zero Hallucination Policy</span>
              </div>
            </div>
          )}

          {activeIndex === 3 && (
            /* Slide 4 Visual: Chronological Webhook State Timeline */
            <div className="rounded-xl border border-[#262F38] bg-[#0B0D0F] p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-[#1F262E] pb-3">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-[#C6F36A]" />
                  <span className="text-xs font-mono font-semibold text-[#F3F5F7]">
                    Webhook State Transition Sequence
                  </span>
                </div>
                <span className="text-[11px] font-mono text-[#9BA5B0] tabular-nums">
                  3 Events Recorded
                </span>
              </div>

              <div className="relative pl-5 space-y-3 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-px before:bg-[#262F38]">
                {[
                  {
                    event: "payment_intent.created",
                    transition: "null → pending",
                    ts: "14:02:11.040 UTC",
                    statusColor: "text-[#9BA5B0]",
                  },
                  {
                    event: "charge.authorized",
                    transition: "pending → authorized",
                    ts: "14:02:12.418 UTC",
                    statusColor: "text-[#60A5FA]",
                  },
                  {
                    event: "capture.gateway_timeout",
                    transition: "authorized → pending_settlement",
                    ts: "14:02:42.904 UTC",
                    statusColor: "text-[#F59E0B]",
                  },
                ].map((ev, i) => (
                  <div
                    key={i}
                    className="relative p-3 rounded-lg bg-[#111519] border border-[#1F262E] flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <span className="absolute -left-[17px] top-4 w-2.5 h-2.5 rounded-full bg-[#C6F36A] border-2 border-[#0B0D0F]" />
                    <div className="flex items-center gap-2.5 font-mono text-xs">
                      <GitCommit className="w-3.5 h-3.5 text-[#6E7A87]" />
                      <span className="text-[#F3F5F7] font-semibold">{ev.event}</span>
                      <span className={`text-[11px] ${ev.statusColor}`}>
                        ({ev.transition})
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-[#6E7A87] tabular-nums">
                      {ev.ts}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeIndex === 4 && (
            /* Slide 5 Visual: Audit Trail & Tenant Isolation Record */
            <div className="rounded-xl border border-[#262F38] bg-[#0B0D0F] p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-[#1F262E] pb-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-[#C6F36A]" />
                  <span className="text-xs font-mono font-semibold text-[#F3F5F7]">
                    Immutable Investigation Evidence Snapshot
                  </span>
                </div>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#171C21] text-[#2DD4BF] border border-[#2DD4BF]/25">
                  TENANT_SCOPED
                </span>
              </div>

              <div className="p-3.5 rounded-lg bg-[#111519] border border-[#1F262E] font-mono text-xs space-y-2 text-[#9BA5B0]">
                <div className="flex justify-between">
                  <span className="text-[#6E7A87]">case_number:</span>
                  <span className="text-[#F3F5F7]">CASE-2026-8841</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#6E7A87]">rbac_scope:</span>
                  <span className="text-[#C6F36A]">created_by_user_id == current_user.id</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#6E7A87]">document_sha256:</span>
                  <span className="text-[#F3F5F7] truncate max-w-[220px]">
                    e3b0c44298fc1c149afbf4c8996fb924...
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#6E7A87]">human_review_required:</span>
                  <span className="text-[#2DD4BF]">false (confidence: 0.94)</span>
                </div>
              </div>

              <div className="flex items-center justify-between text-[11px] text-[#6E7A87] font-mono pt-1">
                <span className="flex items-center gap-1.5">
                  <FileCheck className="w-3.5 h-3.5 text-[#C6F36A]" />
                  Post-commit durable file journal active
                </span>
                <span>PII Sanitization: ENABLED</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Bar: Dot Indicators & Keyboard Hint */}
      <div className="px-6 py-3.5 border-t border-[#1F262E] bg-[#0B0D0F]/50 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {SLIDES.map((s, idx) => (
            <button
              key={s.id}
              type="button"
              onClick={() => goToSlide(idx)}
              aria-label={`Go to slide ${idx + 1}: ${s.title}`}
              className={`h-2 rounded-full transition-all ${
                idx === activeIndex
                  ? "w-7 bg-[#C6F36A]"
                  : "w-2 bg-[#262F38] hover:bg-[#333F4C]"
              }`}
            />
          ))}
        </div>
        <span className="text-[11px] font-mono text-[#6E7A87]">
          Use ← / → arrow keys or swipe horizontally to inspect stages
        </span>
      </div>
    </div>
  );
}
