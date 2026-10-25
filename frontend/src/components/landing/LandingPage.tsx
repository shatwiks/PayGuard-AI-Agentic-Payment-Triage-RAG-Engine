"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  FileSearch,
  Lock,
  Menu,
  Play,
  RotateCcw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  UserCheck,
  X,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { HealthResponse } from "@/lib/types";
import {
  RevealSection,
  SubtleParallax,
  useReducedMotion,
} from "@/components/motion/MotionSystem";
import { FeatureSlider } from "./FeatureSlider";

interface HeroStep {
  step: number;
  label: string;
  badge: string;
  detail: string;
  code: string;
}

const HERO_SEQUENCE: HeroStep[] = [
  {
    step: 1,
    label: "1. Payment Event Telemetry",
    badge: "EVENT_CAPTURED",
    detail:
      "Webhook stream records two identical USD 149.99 authorization holds within 42 seconds on card rail.",
    code: "ref: tx_20261020_0001 • status: authorized • events: 2",
  },
  {
    step: 2,
    label: "2. Deterministic Triage Status",
    badge: "TRIAGED • 94% CONFIDENCE",
    detail:
      "TriageRulesEngine classifies case as duplicate_charges / authorization_holds before invoking LLM synthesis.",
    code: "category: duplicate_charges • human_review: false",
  },
  {
    step: 3,
    label: "3. Hybrid Policy Retrieval",
    badge: "PGVECTOR + FTS RRF",
    detail:
      "HybridRetrievalService ranks 1536-d nomic-embed-text vectors alongside PostgreSQL FTS lexical matches.",
    code: "mode: hybrid • top_fusion_score: 0.0328",
  },
  {
    step: 4,
    label: "4. Grounded Evidence Citation",
    badge: "VERIFIED EXCERPT",
    detail:
      "Merchant Billing Policy (Sec 3.2): Duplicate authorization holds without settlement capture must be voided within 24 hours.",
    code: "source: MBP-2026-SEC-3.2 • grounded: true",
  },
  {
    step: 5,
    label: "5. Final Investigation State",
    badge: "ACTION: VOID_HOLD",
    detail:
      "Prescribes VOID_AUTHORIZATION_HOLD with full evidence package persisted to immutable case record.",
    code: "case_status: triaged • audit_event: persisted",
  },
];

const STORY_STEPS = [
  {
    id: "story-lookup",
    stepNumber: "01",
    title: "Locate the transaction & inspect raw gateway events",
    description:
      "Start with a payment reference or customer dispute description. PayGuard AI queries the PostgreSQL transaction ledger and reconstructs every state transition and webhook payload.",
    endpoint: "GET /api/v1/payments/by-reference/{reference}",
    metrics: [
      { label: "Supported Rails", value: "Card, ACH, UPI, Debit" },
      { label: "Event Ordering", value: "Chronological UTC" },
    ],
  },
  {
    id: "story-triage",
    stepNumber: "02",
    title: "Classify deterministically before generative reasoning",
    description:
      "Instead of letting an LLM guess transaction states, TriageRulesEngine deterministically evaluates payment status, processor failure codes, and dispute tokens to assign an issue category and confidence score.",
    endpoint: "TriageRulesEngine.evaluate()",
    metrics: [
      { label: "Classification", value: "Deterministic Rules" },
      { label: "Escalation Guard", value: "Auto-flags ambiguity" },
    ],
  },
  {
    id: "story-rag",
    stepNumber: "03",
    title: "Retrieve scheme rules & tenant-scoped compliance docs",
    description:
      "HybridRetrievalService executes Reciprocal Rank Fusion across pgvector cosine similarity and PostgreSQL Full-Text Search, respecting strict tenant ownership on uploaded documents.",
    endpoint: "POST /api/v1/knowledge/search • /knowledge/ask",
    metrics: [
      { label: "Vector Dimension", value: "1536 (pgvector)" },
      { label: "Fusion Method", value: "Reciprocal Rank (RRF)" },
    ],
  },
  {
    id: "story-grounding",
    stepNumber: "04",
    title: "Verify grounding specificity or safely abstain",
    description:
      "GroundingVerifier validates that rule identifiers, modal predicates, and query subjects actually exist in the cited text. When evidence is absent or mismatched, PayGuard AI explicitly abstains.",
    endpoint: "GroundingVerifier.verify_qa_grounding()",
    metrics: [
      { label: "Unsupported Queries", value: "Explicit Abstention" },
      { label: "Citation Provenance", value: "Chunk + Section + Hash" },
    ],
  },
];

export function LandingPage() {
  const { isAuthenticated, user } = useAuth();
  const reducedMotion = useReducedMotion();

  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  // Hero controlled sequence state (1..5)
  const [activeHeroStep, setActiveHeroStep] = useState<number>(5);
  const [isReplayingHero, setIsReplayingHero] = useState<boolean>(false);

  // Sticky storytelling active stage (0..3)
  const [activeStoryStep, setActiveStoryStep] = useState<number>(0);
  const storyRefs = useRef<(HTMLDivElement | null)[]>([]);
  const mobileMenuRef = useRef<HTMLDivElement | null>(null);

  // Check real backend health status (non-blocking)
  useEffect(() => {
    let mounted = true;
    api
      .getHealth()
      .then((res) => {
        if (mounted) setHealth(res);
      })
      .catch(() => {
        // Keep null if backend is unreachable; never fake health
      });
    return () => {
      mounted = false;
    };
  }, []);

  // Scroll listener for navbar background elevation
  useEffect(() => {
    const onScroll = () => {
      setScrolled(window.scrollY > 16);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Initial controlled hero sequence playthrough (unless reduced motion is enabled)
  useEffect(() => {
    if (reducedMotion) {
      setActiveHeroStep(5);
      setIsReplayingHero(false);
      return;
    }

    setActiveHeroStep(1);
    setIsReplayingHero(true);

    const timers: NodeJS.Timeout[] = [];
    for (let step = 2; step <= 5; step++) {
      timers.push(
        setTimeout(() => {
          setActiveHeroStep(step);
          if (step === 5) setIsReplayingHero(false);
        }, (step - 1) * 750)
      );
    }

    return () => timers.forEach(clearTimeout);
  }, [reducedMotion]);

  const replayHeroSequence = () => {
    if (reducedMotion) {
      setActiveHeroStep(5);
      return;
    }
    setActiveHeroStep(1);
    setIsReplayingHero(true);
    for (let step = 2; step <= 5; step++) {
      setTimeout(() => {
        setActiveHeroStep(step);
        if (step === 5) setIsReplayingHero(false);
      }, (step - 1) * 650);
    }
  };

  // Observe sticky storytelling steps
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const observers: IntersectionObserver[] = [];

    storyRefs.current.forEach((el, index) => {
      if (!el) return;
      const obs = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              setActiveStoryStep(index);
            }
          });
        },
        { threshold: 0.45, rootMargin: "-15% 0px -25% 0px" }
      );
      obs.observe(el);
      observers.push(obs);
    });

    return () => observers.forEach((o) => o.disconnect());
  }, []);

  // Close mobile menu on Escape key
  useEffect(() => {
    if (!mobileMenuOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mobileMenuOpen]);

  const primaryCtaHref = isAuthenticated
    ? "/investigations/new"
    : "/login?redirect=%2Finvestigations%2Fnew";

  const dashboardHref = isAuthenticated ? "/" : "/login";

  return (
    <div className="min-h-[100dvh] bg-[#0B0D0F] text-[#F3F5F7] flex flex-col selection:bg-[#C6F36A]/20">
      {/* Skip to main content link for keyboard accessibility */}
      <a
        href="#main-landing-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:rounded-lg focus:bg-[#C6F36A] focus:text-[#0B0D0F] focus:font-semibold focus:text-xs"
      >
        Skip to content
      </a>

      {/* A. Navigation Bar */}
      <header
        className={`sticky top-0 z-40 h-16 transition-colors duration-200 ${
          scrolled
            ? "bg-[#0B0D0F]/90 backdrop-blur-md border-b border-[#1F262E]"
            : "bg-transparent border-b border-transparent"
        }`}
      >
        <div className="max-w-7xl mx-auto h-full px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4">
          {/* Brand Mark */}
          <Link
            href={isAuthenticated ? "/" : "/welcome"}
            className="flex items-center gap-2.5 group"
          >
            <div className="w-8 h-8 rounded-lg bg-[#171C21] border border-[#C6F36A]/40 flex items-center justify-center text-[#C6F36A] group-hover:border-[#C6F36A] transition">
              <ShieldAlert className="w-4 h-4" />
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="font-bold tracking-tight text-base text-[#F3F5F7]">
                PayGuard
              </span>
              <span className="font-mono text-[11px] font-semibold text-[#C6F36A] px-1.5 py-0.5 rounded bg-[#C6F36A]/10 border border-[#C6F36A]/25">
                AI
              </span>
            </div>
          </Link>

          {/* Desktop Navigation Links */}
          <nav
            aria-label="Primary landing navigation"
            className="hidden md:flex items-center gap-7 text-xs font-medium text-[#9BA5B0]"
          >
            <a href="#product" className="hover:text-[#F3F5F7] transition">
              Product
            </a>
            <a href="#capabilities" className="hover:text-[#F3F5F7] transition">
              Capabilities
            </a>
            <a href="#how-it-works" className="hover:text-[#F3F5F7] transition">
              How It Works
            </a>
            <a href="#security" className="hover:text-[#F3F5F7] transition">
              Security
            </a>
          </nav>

          {/* Desktop Auth / Workspace Actions */}
          <div className="hidden md:flex items-center gap-3">
            {isAuthenticated ? (
              <>
                <Link
                  href="/"
                  className="px-3.5 py-1.5 rounded-lg border border-[#262F38] bg-[#111519] hover:bg-[#171C21] text-xs font-medium text-[#F3F5F7] transition"
                >
                  Console ({user?.full_name || "Operator"})
                </Link>
                <Link
                  href="/investigations/new"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#C6F36A] hover:bg-[#D4F788] text-[#0B0D0F] text-xs font-semibold transition active:scale-[0.98]"
                >
                  <span>Open Investigation</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  className="px-3.5 py-2 rounded-lg text-xs font-medium text-[#9BA5B0] hover:text-[#F3F5F7] transition"
                >
                  Sign In
                </Link>
                <Link
                  href="/register"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#C6F36A] hover:bg-[#D4F788] text-[#0B0D0F] text-xs font-semibold transition active:scale-[0.98]"
                >
                  <span>Get Started</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </>
            )}
          </div>

          {/* Mobile Hamburger Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen((prev) => !prev)}
            aria-expanded={mobileMenuOpen}
            aria-controls="mobile-landing-nav"
            aria-label={mobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
            className="md:hidden p-2 rounded-lg border border-[#262F38] bg-[#111519] text-[#F3F5F7]"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div
            id="mobile-landing-nav"
            ref={mobileMenuRef}
            role="dialog"
            aria-label="Mobile navigation menu"
            className="md:hidden border-b border-[#262F38] bg-[#111519] px-4 pt-3 pb-6 space-y-4 shadow-2xl"
          >
            <div className="flex flex-col space-y-2 text-sm font-medium text-[#F3F5F7]">
              <a
                href="#product"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2 rounded-lg hover:bg-[#171C21]"
              >
                Product
              </a>
              <a
                href="#capabilities"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2 rounded-lg hover:bg-[#171C21]"
              >
                Capabilities
              </a>
              <a
                href="#how-it-works"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2 rounded-lg hover:bg-[#171C21]"
              >
                How It Works
              </a>
              <a
                href="#security"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2 rounded-lg hover:bg-[#171C21]"
              >
                Security
              </a>
            </div>

            <div className="pt-3 border-t border-[#1F262E] flex flex-col gap-2.5">
              {isAuthenticated ? (
                <>
                  <Link
                    href="/"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full py-2.5 px-4 rounded-lg border border-[#262F38] bg-[#171C21] text-center text-xs font-semibold text-[#F3F5F7]"
                  >
                    Return to Operations Console
                  </Link>
                  <Link
                    href="/investigations/new"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full py-2.5 px-4 rounded-lg bg-[#C6F36A] text-[#0B0D0F] text-center text-xs font-semibold"
                  >
                    Open Investigation
                  </Link>
                </>
              ) : (
                <>
                  <Link
                    href="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full py-2.5 px-4 rounded-lg border border-[#262F38] bg-[#171C21] text-center text-xs font-semibold text-[#F3F5F7]"
                  >
                    Sign In
                  </Link>
                  <Link
                    href="/register"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full py-2.5 px-4 rounded-lg bg-[#C6F36A] text-[#0B0D0F] text-center text-xs font-semibold"
                  >
                    Get Started
                  </Link>
                </>
              )}
            </div>
          </div>
        )}
      </header>

      <main id="main-landing-content" className="flex-1">
        {/* B. Hero Section */}
        <section className="relative pt-10 pb-20 lg:pt-16 lg:pb-28 border-b border-[#1F262E] pg-tech-grid overflow-hidden">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            {/* Left Column: Hero Messaging & CTAs */}
            <div className="lg:col-span-6 space-y-6">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-md bg-[#111519] border border-[#262F38] text-xs font-mono text-[#9BA5B0]">
                <span
                  className={`w-2 h-2 rounded-full ${
                    health?.status === "healthy"
                      ? "bg-[#2DD4BF]"
                      : "bg-[#C6F36A]"
                  }`}
                />
                <span className="text-[#C6F36A] font-semibold">
                  AGENTIC PAYMENT TRIAGE &amp; GROUNDED RAG
                </span>
                {health && (
                  <span className="text-[#6E7A87]">
                    • {health.vector_store} ({health.environment})
                  </span>
                )}
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-[52px] font-bold tracking-tight text-[#F3F5F7] leading-[1.08] text-balance">
                Investigate payment failures. Find the evidence. Act with confidence.
              </h1>

              <p className="text-base sm:text-lg text-[#9BA5B0] leading-relaxed max-w-[56ch]">
                Trace payment events, retrieve relevant policies, and investigate transaction issues with evidence-grounded AI.
              </p>

              <div className="flex flex-wrap items-center gap-3.5 pt-2">
                <Link
                  href={primaryCtaHref}
                  className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-[#C6F36A] hover:bg-[#D4F788] text-[#0B0D0F] text-sm font-semibold transition active:scale-[0.98]"
                >
                  <span>Open Investigation</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <a
                  href="#how-it-works"
                  className="inline-flex items-center gap-2 px-5 py-3 rounded-xl border border-[#262F38] bg-[#111519] hover:bg-[#171C21] hover:border-[#333F4C] text-sm font-medium text-[#F3F5F7] transition"
                >
                  <span>Explore the Workflow</span>
                </a>
              </div>

              {/* Technical Architecture Facts (No fake stats or fabricated logos) */}
              <div className="pt-6 border-t border-[#1F262E] grid grid-cols-3 gap-4 text-xs">
                <div>
                  <span className="font-mono text-[#C6F36A] font-semibold block">
                    pgvector + FTS
                  </span>
                  <span className="text-[#6E7A87] mt-0.5 block">
                    Reciprocal Rank Fusion
                  </span>
                </div>
                <div>
                  <span className="font-mono text-[#F3F5F7] font-semibold block">
                    Rule-ID Verified
                  </span>
                  <span className="text-[#6E7A87] mt-0.5 block">
                    Strict Abstention Guard
                  </span>
                </div>
                <div>
                  <span className="font-mono text-[#2DD4BF] font-semibold block">
                    Read-Only Ledger
                  </span>
                  <span className="text-[#6E7A87] mt-0.5 block">
                    No Autonomous Execution
                  </span>
                </div>
              </div>
            </div>

            {/* Right Column: Interactive Hero Investigation Visualization */}
            <div className="lg:col-span-6">
              <div className="pg-surface-shell">
                <div className="pg-surface-core p-5 sm:p-6 space-y-4">
                  {/* Top Bar: Explicit Illustrative Label & Replay Control */}
                  <div className="flex flex-wrap items-center justify-between gap-2 pb-3.5 border-b border-[#1F262E]">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-[#171C21] border border-[#262F38] text-[10px] font-mono uppercase tracking-wider text-[#9BA5B0]">
                        Illustrative Example
                      </span>
                      <span className="text-xs font-mono text-[#F3F5F7] font-semibold">
                        CASE-DEMO-0001
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={replayHeroSequence}
                        aria-label="Replay investigation sequence animation"
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-[#262F38] bg-[#171C21] hover:bg-[#1D242B] text-[11px] font-mono text-[#C6F36A] transition"
                      >
                        <RotateCcw
                          className={`w-3 h-3 ${
                            isReplayingHero && !reducedMotion ? "animate-spin" : ""
                          }`}
                        />
                        <span>Replay Sequence</span>
                      </button>
                    </div>
                  </div>

                  {/* Step Selector Pills */}
                  <div
                    className="grid grid-cols-5 gap-1.5"
                    role="group"
                    aria-label="Investigation sequence stages"
                  >
                    {HERO_SEQUENCE.map((item) => {
                      const reached = activeHeroStep >= item.step;
                      const isCurrent = activeHeroStep === item.step;
                      return (
                        <button
                          key={item.step}
                          type="button"
                          onClick={() => {
                            setIsReplayingHero(false);
                            setActiveHeroStep(item.step);
                          }}
                          className={`py-1.5 px-2 rounded-md text-left border transition ${
                            isCurrent
                              ? "bg-[#171C21] border-[#C6F36A] text-[#C6F36A]"
                              : reached
                              ? "bg-[#171C21]/60 border-[#262F38] text-[#F3F5F7]"
                              : "bg-[#0B0D0F] border-[#1F262E] text-[#6E7A87]"
                          }`}
                        >
                          <span className="text-[10px] font-mono block">
                            0{item.step}
                          </span>
                        </button>
                      );
                    })}
                  </div>

                  {/* Controlled Sequence Cards */}
                  <div className="space-y-2.5">
                    {HERO_SEQUENCE.map((item) => {
                      const isReached = activeHeroStep >= item.step;
                      const isCurrent = activeHeroStep === item.step;
                      return (
                        <div
                          key={item.step}
                          onClick={() => setActiveHeroStep(item.step)}
                          className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-300 ${
                            isCurrent
                              ? "bg-[#171C21] border-[#C6F36A]/45 shadow-md"
                              : isReached
                              ? "bg-[#0B0D0F]/90 border-[#262F38] opacity-95"
                              : "bg-[#0B0D0F]/40 border-[#1F262E] opacity-40"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-semibold text-[#F3F5F7] flex items-center gap-2">
                              <CheckCircle2
                                className={`w-3.5 h-3.5 shrink-0 ${
                                  isReached ? "text-[#C6F36A]" : "text-[#6E7A87]"
                                }`}
                              />
                              {item.label}
                            </span>
                            <span
                              className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                                isCurrent
                                  ? "bg-[#C6F36A]/10 text-[#C6F36A] border-[#C6F36A]/30"
                                  : "bg-[#111519] text-[#9BA5B0] border-[#262F38]"
                              }`}
                            >
                              {item.badge}
                            </span>
                          </div>
                          <p className="text-xs text-[#9BA5B0] mt-1.5 pl-5.5 leading-relaxed">
                            {item.detail}
                          </p>
                          <div className="mt-2 pl-5.5">
                            <code className="text-[11px] font-mono text-[#6E7A87] block">
                              {item.code}
                            </code>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div className="pt-2 border-t border-[#1F262E] flex items-center justify-between text-[11px] text-[#6E7A87] font-mono">
                    <span>Self-contained pre-login illustration</span>
                    <Link
                      href={dashboardHref}
                      className="text-[#C6F36A] hover:underline"
                    >
                      Run against live database &rarr;
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* C. Interactive Feature Slider Section */}
        <section id="capabilities" className="py-20 lg:py-28 border-b border-[#1F262E]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
            <RevealSection className="max-w-2xl space-y-3">
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#F3F5F7]">
                Engineered for payment operations & dispute analysts
              </h2>
              <p className="text-sm sm:text-base text-[#9BA5B0] leading-relaxed">
                Explore the five core subsystems powering PayGuard AI. Use the interactive controls, keyboard arrows, or touch gestures to inspect each operational layer.
              </p>
            </RevealSection>

            <RevealSection delayMs={80}>
              <FeatureSlider />
            </RevealSection>
          </div>
        </section>

        {/* D. Sticky Storytelling Section (#product) */}
        <section id="product" className="py-20 lg:py-28 border-b border-[#1F262E] bg-[#0B0D0F]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <RevealSection className="max-w-2xl space-y-3 mb-14">
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#F3F5F7]">
                From raw gateway webhook to verifiable policy citation
              </h2>
              <p className="text-sm sm:text-base text-[#9BA5B0] leading-relaxed">
                As you scroll through each stage below, inspect how PayGuard AI separates confirmed payment facts, deterministic rules, and grounded policy retrieval.
              </p>
            </RevealSection>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
              {/* Left Column: Scrolling Narrative Steps */}
              <div className="lg:col-span-5 space-y-12 lg:space-y-24">
                {STORY_STEPS.map((step, index) => {
                  const isActive = activeStoryStep === index;
                  return (
                    <div
                      key={step.id}
                      ref={(el) => {
                        storyRefs.current[index] = el;
                      }}
                      onClick={() => setActiveStoryStep(index)}
                      className={`cursor-pointer rounded-2xl border p-6 transition-all duration-300 ${
                        isActive
                          ? "bg-[#111519] border-[#C6F36A]/45 shadow-lg"
                          : "bg-[#111519]/50 border-[#1F262E] hover:border-[#262F38]"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <span
                          className={`font-mono text-xs font-bold px-2.5 py-1 rounded ${
                            isActive
                              ? "bg-[#C6F36A] text-[#0B0D0F]"
                              : "bg-[#171C21] text-[#9BA5B0]"
                          }`}
                        >
                          STEP {step.stepNumber}
                        </span>
                        <span className="text-[11px] font-mono text-[#6E7A87]">
                          {step.endpoint}
                        </span>
                      </div>

                      <h3 className="text-xl font-bold text-[#F3F5F7] mb-2">
                        {step.title}
                      </h3>
                      <p className="text-sm text-[#9BA5B0] leading-relaxed mb-5">
                        {step.description}
                      </p>

                      <div className="grid grid-cols-2 gap-3 pt-4 border-t border-[#1F262E]">
                        {step.metrics.map((m, idx) => (
                          <div key={idx}>
                            <span className="text-[10px] font-mono uppercase text-[#6E7A87] block">
                              {m.label}
                            </span>
                            <span className="text-xs font-mono font-semibold text-[#F3F5F7] mt-0.5 block">
                              {m.value}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Right Column: Sticky Evolving Investigation Visualization */}
              <div className="lg:col-span-7 lg:sticky lg:top-24">
                <SubtleParallax maxShiftPx={10}>
                  <div className="pg-surface-shell">
                    <div className="pg-surface-core p-6 sm:p-8 space-y-6">
                      <div className="flex flex-wrap items-center justify-between gap-2 pb-4 border-b border-[#1F262E]">
                        <div className="flex items-center gap-2.5">
                          <div className="w-2.5 h-2.5 rounded-full bg-[#C6F36A]" />
                          <span className="text-xs font-mono font-semibold text-[#F3F5F7]">
                            ACTIVE STAGE {STORY_STEPS[activeStoryStep].stepNumber}:{" "}
                            {STORY_STEPS[activeStoryStep].endpoint}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          {STORY_STEPS.map((s, idx) => (
                            <button
                              key={s.id}
                              type="button"
                              onClick={() => setActiveStoryStep(idx)}
                              className={`px-2 py-0.5 rounded text-[11px] font-mono transition ${
                                activeStoryStep === idx
                                  ? "bg-[#C6F36A] text-[#0B0D0F] font-bold"
                                  : "bg-[#171C21] text-[#9BA5B0] hover:text-[#F3F5F7]"
                              }`}
                            >
                              {s.stepNumber}
                            </button>
                          ))}
                        </div>
                      </div>

                      {activeStoryStep === 0 && (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between text-xs font-mono text-[#9BA5B0]">
                            <span>CONFIRMED DATABASE FACTS</span>
                            <span className="text-[#2DD4BF]">PostgreSQL Verified</span>
                          </div>
                          <div className="p-4 rounded-xl bg-[#0B0D0F] border border-[#262F38] font-mono text-xs space-y-2.5">
                            <div className="flex justify-between">
                              <span className="text-[#6E7A87]">payment_reference</span>
                              <span className="text-[#F3F5F7]">tx_20261020_0004</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-[#6E7A87]">amount / currency</span>
                              <span className="text-[#C6F36A] tabular-nums">USD 420.00</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-[#6E7A87]">status</span>
                              <span className="text-[#F87171]">disputed</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-[#6E7A87]">gateway_failure_code</span>
                              <span className="text-[#F59E0B]">visa_condition_13_1</span>
                            </div>
                          </div>
                          <p className="text-xs text-[#9BA5B0]">
                            Payment facts are queried directly from relational tables—never inferred by generative models.
                          </p>
                        </div>
                      )}

                      {activeStoryStep === 1 && (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between text-xs font-mono text-[#9BA5B0]">
                            <span>SYSTEM CLASSIFICATION</span>
                            <span className="text-[#C6F36A]">Deterministic Rule Match</span>
                          </div>
                          <div className="p-4 rounded-xl bg-[#0B0D0F] border border-[#262F38] space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-mono text-[#6E7A87]">
                                Issue Category
                              </span>
                              <span className="text-xs font-mono font-bold text-[#F3F5F7] bg-[#171C21] px-2.5 py-1 rounded border border-[#262F38]">
                                chargebacks_disputes
                              </span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-mono text-[#6E7A87]">
                                Recommended Action
                              </span>
                              <span className="text-xs font-mono font-bold text-[#C6F36A] bg-[#C6F36A]/10 px-2.5 py-1 rounded border border-[#C6F36A]/30">
                                SUBMIT_COMPELLING_EVIDENCE
                              </span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-mono text-[#6E7A87]">
                                Human Review Flag
                              </span>
                              <span className="text-xs font-mono text-[#F59E0B]">
                                true (Dispute threshold check)
                              </span>
                            </div>
                          </div>
                        </div>
                      )}

                      {activeStoryStep === 2 && (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between text-xs font-mono text-[#9BA5B0]">
                            <span>HYBRID KNOWLEDGE RETRIEVAL</span>
                            <span className="text-[#60A5FA]">RRF Fusion Top-K</span>
                          </div>
                          <div className="space-y-2.5">
                            <div className="p-3.5 rounded-xl bg-[#0B0D0F] border border-[#C6F36A]/35 space-y-1.5">
                              <div className="flex items-center justify-between text-[11px] font-mono">
                                <span className="text-[#C6F36A] font-semibold">
                                  Rank #1 • Visa Core Rules: Condition 13.1
                                </span>
                                <span className="text-[#9BA5B0] tabular-nums">
                                  Fusion: 0.0328
                                </span>
                              </div>
                              <p className="text-xs text-[#F3F5F7]/90 italic">
                                &ldquo;Merchandise/Services Not Received claims require shipping carrier delivery confirmation within the compulsory response window.&rdquo;
                              </p>
                            </div>
                            <div className="p-3.5 rounded-xl bg-[#0B0D0F] border border-[#1F262E] space-y-1">
                              <div className="flex items-center justify-between text-[11px] font-mono text-[#9BA5B0]">
                                <span>Tenant Isolation Boundary</span>
                                <span className="text-[#2DD4BF]">Enforced</span>
                              </div>
                              <p className="text-xs text-[#6E7A87]">
                                Queries filter strictly by `is_system = true OR uploaded_by_id = current_user.id`.
                              </p>
                            </div>
                          </div>
                        </div>
                      )}

                      {activeStoryStep === 3 && (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between text-xs font-mono text-[#9BA5B0]">
                            <span>GROUNDING VERIFICATION & ABSTENTION</span>
                            <span className="text-[#2DD4BF]">GroundingVerifier</span>
                          </div>
                          <div className="p-4 rounded-xl bg-[#0B0D0F] border border-[#262F38] space-y-3 text-xs">
                            <div className="flex items-start gap-2.5">
                              <CheckCircle2 className="w-4 h-4 text-[#2DD4BF] shrink-0 mt-0.5" />
                              <div>
                                <span className="font-semibold text-[#F3F5F7] block">
                                  Rule-ID & Subject Alignment Checked
                                </span>
                                <span className="text-[#9BA5B0]">
                                  Verifies that cited rule codes and query subjects co-occur in the selected evidence sentences.
                                </span>
                              </div>
                            </div>
                            <div className="flex items-start gap-2.5">
                              <ShieldAlert className="w-4 h-4 text-[#F59E0B] shrink-0 mt-0.5" />
                              <div>
                                <span className="font-semibold text-[#F3F5F7] block">
                                  Explicit Abstention on Missing Evidence
                                </span>
                                <span className="text-[#9BA5B0]">
                                  When a user asks about an unsupported rail or absent clause, `has_sufficient_evidence` returns `false` with zero fabricated citations.
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </SubtleParallax>
              </div>
            </div>
          </div>
        </section>

        {/* E. How It Works — 6-Stage Animated Process Timeline */}
        <section id="how-it-works" className="py-20 lg:py-28 border-b border-[#1F262E]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
            <RevealSection className="max-w-2xl space-y-3">
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#F3F5F7]">
                Six-stage investigation lifecycle
              </h2>
              <p className="text-sm sm:text-base text-[#9BA5B0] leading-relaxed">
                Every investigation follows the exact orchestration pipeline implemented in{" "}
                <code className="text-xs font-mono text-[#C6F36A]">
                  OrchestrationService.run_investigation()
                </code>
                .
              </p>
            </RevealSection>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {[
                {
                  step: "01",
                  title: "Identify the payment",
                  body: "Validate the payment reference or UUID against PostgreSQL and load customer, merchant, rail, and processor metadata.",
                  icon: <Search className="w-4 h-4 text-[#C6F36A]" />,
                },
                {
                  step: "02",
                  title: "Retrieve payment events",
                  body: "Fetch the chronological sequence of webhook state transitions and processor failure payloads.",
                  icon: <Clock className="w-4 h-4 text-[#C6F36A]" />,
                },
                {
                  step: "03",
                  title: "Classify the issue",
                  body: "Execute deterministic triage rules over payment status, failure codes, and sanitized query text to compute category and confidence.",
                  icon: <Cpu className="w-4 h-4 text-[#C6F36A]" />,
                },
                {
                  step: "04",
                  title: "Search knowledge & policies",
                  body: "Run hybrid Reciprocal Rank Fusion across pgvector embeddings and PostgreSQL FTS within the operator's authorized scope.",
                  icon: <Database className="w-4 h-4 text-[#C6F36A]" />,
                },
                {
                  step: "05",
                  title: "Produce grounded explanation",
                  body: "Synthesize root-cause findings backed strictly by retrieved policy excerpts, or abstain when evidence is insufficient.",
                  icon: <BookOpen className="w-4 h-4 text-[#C6F36A]" />,
                },
                {
                  step: "06",
                  title: "Review evidence & audit record",
                  body: "Persist the investigation case, policy citations, execution latency, and immutable evidence package for analyst review.",
                  icon: <FileSearch className="w-4 h-4 text-[#C6F36A]" />,
                },
              ].map((item, idx) => (
                <RevealSection
                  key={item.step}
                  delayMs={idx * 60}
                  className="rounded-xl border border-[#1F262E] bg-[#111519] p-6 flex flex-col justify-between space-y-4 hover:border-[#333F4C] transition"
                >
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-[#C6F36A] bg-[#C6F36A]/10 border border-[#C6F36A]/25 px-2.5 py-0.5 rounded">
                        STAGE {item.step}
                      </span>
                      <div className="p-2 rounded-lg bg-[#171C21] border border-[#262F38]">
                        {item.icon}
                      </div>
                    </div>
                    <h3 className="text-base font-bold text-[#F3F5F7]">
                      {item.title}
                    </h3>
                    <p className="text-xs text-[#9BA5B0] leading-relaxed">
                      {item.body}
                    </p>
                  </div>
                </RevealSection>
              ))}
            </div>

            {/* Mandatory Operational Disclaimer */}
            <RevealSection className="rounded-xl border border-[#262F38] bg-[#111519] p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <ShieldAlert className="w-5 h-5 text-[#F59E0B] shrink-0 mt-0.5" />
                <p className="text-xs text-[#9BA5B0] leading-relaxed">
                  <strong className="text-[#F3F5F7]">Operational Boundary Notice:</strong>{" "}
                  AI-generated explanations and triage recommendations provide evidence-based investigative assistance. They do not represent guaranteed financial outcomes and never execute autonomous settlement, refund, or ledger mutations.
                </p>
              </div>
              <Link
                href={primaryCtaHref}
                className="px-4 py-2 rounded-lg bg-[#171C21] hover:bg-[#1D242B] border border-[#262F38] text-xs font-semibold text-[#C6F36A] shrink-0 transition"
              >
                Launch Workspace &rarr;
              </Link>
            </RevealSection>
          </div>
        </section>

        {/* F. Verifiable Security & Trust Section (#security) */}
        <section id="security" className="py-20 lg:py-28 border-b border-[#1F262E]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
            <RevealSection className="max-w-2xl space-y-3">
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#F3F5F7]">
                Verifiable application security & tenant controls
              </h2>
              <p className="text-sm sm:text-base text-[#9BA5B0] leading-relaxed">
                Every control listed below is directly implemented and tested in the PayGuard AI repository—without unverified compliance or certification claims.
              </p>
            </RevealSection>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {[
                {
                  title: "Authentication & RBAC",
                  description:
                    "JWT bearer authentication with role-based access scoping across support_agent, compliance_analyst, and admin personas.",
                  icon: <UserCheck className="w-4 h-4 text-[#2DD4BF]" />,
                  code: "backend/app/core/security.py",
                },
                {
                  title: "Strict Tenant Isolation",
                  description:
                    "Uploaded compliance documents and private investigation cases are scoped to the creating user ID; unauthorized cross-tenant lookups return 404/403.",
                  icon: <Lock className="w-4 h-4 text-[#2DD4BF]" />,
                  code: "backend/app/api/knowledge.py",
                },
                {
                  title: "Verifiable Evidence Citations",
                  description:
                    "Every grounded answer returns the exact document ID, chunk ID, section header, and verbatim passage used during synthesis.",
                  icon: <BookOpen className="w-4 h-4 text-[#2DD4BF]" />,
                  code: "backend/app/services/document_qa.py",
                },
                {
                  title: "Safe Abstention on Insufficient Evidence",
                  description:
                    "GroundingVerifier blocks answers when rule IDs, numbers, or subjects in the query are unsupported by retrieved chunks.",
                  icon: <ShieldCheck className="w-4 h-4 text-[#2DD4BF]" />,
                  code: "backend/app/services/grounding.py",
                },
                {
                  title: "Investigation vs. Execution Separation",
                  description:
                    "Payment endpoints are strictly read-only (`GET /payments`). PayGuard AI recommends operational actions without mutating processor balances.",
                  icon: <Activity className="w-4 h-4 text-[#2DD4BF]" />,
                  code: "backend/app/api/payments.py",
                },
                {
                  title: "Rate Limiting & Proxy Verification",
                  description:
                    "Sliding-window rate limiting with CIDR-verified trusted proxy IP extraction and fail-closed Redis policy support.",
                  icon: <Terminal className="w-4 h-4 text-[#2DD4BF]" />,
                  code: "backend/app/core/rate_limit.py",
                },
              ].map((sec, i) => (
                <RevealSection
                  key={sec.title}
                  delayMs={i * 50}
                  className="rounded-xl border border-[#1F262E] bg-[#111519] p-6 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div className="p-2 rounded-lg bg-[#171C21] border border-[#262F38]">
                      {sec.icon}
                    </div>
                    <span className="text-[11px] font-mono text-[#6E7A87]">
                      {sec.code}
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-[#F3F5F7]">
                    {sec.title}
                  </h3>
                  <p className="text-xs text-[#9BA5B0] leading-relaxed">
                    {sec.description}
                  </p>
                </RevealSection>
              ))}
            </div>
          </div>
        </section>
      </main>

      {/* G. Footer */}
      <footer className="bg-[#0B0D0F] border-t border-[#1F262E] py-12 text-xs text-[#9BA5B0]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div className="space-y-3 md:col-span-2">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-[#171C21] border border-[#C6F36A]/40 flex items-center justify-center text-[#C6F36A]">
                  <ShieldAlert className="w-4 h-4" />
                </div>
                <span className="font-bold text-sm text-[#F3F5F7]">
                  PayGuard AI
                </span>
              </div>
              <p className="text-xs text-[#6E7A87] max-w-sm leading-relaxed">
                Agentic Payment Triage & Evidence-Grounded RAG Engine for payment operations and dispute investigation teams.
              </p>
            </div>

            <div className="space-y-2.5">
              <span className="font-mono text-[11px] uppercase tracking-wider text-[#F3F5F7] font-semibold block">
                Platform
              </span>
              <ul className="space-y-2">
                <li>
                  <a href="#product" className="hover:text-[#F3F5F7] transition">
                    Product Architecture
                  </a>
                </li>
                <li>
                  <a href="#capabilities" className="hover:text-[#F3F5F7] transition">
                    Interactive Capabilities
                  </a>
                </li>
                <li>
                  <Link href="/knowledge" className="hover:text-[#F3F5F7] transition">
                    Knowledge & Rule Explorer
                  </Link>
                </li>
                <li>
                  <Link href="/login" className="hover:text-[#F3F5F7] transition">
                    Operator Sign In
                  </Link>
                </li>
              </ul>
            </div>

            <div className="space-y-2.5">
              <span className="font-mono text-[11px] uppercase tracking-wider text-[#F3F5F7] font-semibold block">
                Governance & Legal Notices
              </span>
              <ul className="space-y-2">
                <li>
                  <Link href="/privacy" className="hover:text-[#F3F5F7] transition">
                    Privacy Policy (Draft Notice)
                  </Link>
                </li>
                <li>
                  <Link href="/terms" className="hover:text-[#F3F5F7] transition">
                    Terms & Conditions (Draft Notice)
                  </Link>
                </li>
                <li>
                  <a href="#security" className="hover:text-[#F3F5F7] transition">
                    Verified Security Controls
                  </a>
                </li>
              </ul>
            </div>
          </div>

          <div className="pt-6 border-t border-[#1F262E] flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px] text-[#6E7A87]">
            <span>
              PayGuard AI — Evidence-Grounded Financial Investigation Workspace
            </span>
            <span className="font-mono">
              FastAPI • PostgreSQL pgvector • Next.js App Router
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
