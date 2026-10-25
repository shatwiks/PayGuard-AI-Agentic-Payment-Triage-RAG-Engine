"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Check,
  Copy,
  ExternalLink,
  FileText,
  Layers,
  ShieldCheck,
  X,
} from "lucide-react";

export interface EvidenceCitationData {
  title: string;
  section: string;
  excerpt: string;
  score?: number | null;
  scoreLabel?: string | null;
  sourceId?: string | null;
  sourceUrl?: string | null;
  documentId?: string | null;
  chunkId?: string | null;
  page?: number | null;
  docType?: string | null;
  retrievalMode?: string | null;
}

export type EvidenceDrawerItem = EvidenceCitationData;

interface EvidenceDrawerProps {
  citation?: EvidenceCitationData | null;
  evidence?: EvidenceCitationData | null;
  isOpen?: boolean;
  onClose: () => void;
}

/**
 * Reusable slide-over evidence & citation inspector.
 * Displays authoritative grounding metadata, verbatim passage highlight, and copy/verification controls.
 */
export function EvidenceDrawer({
  citation: citationProp,
  evidence,
  isOpen,
  onClose,
}: EvidenceDrawerProps) {
  const citation = isOpen === false ? null : citationProp ?? evidence ?? null;
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const [copiedExcerpt, setCopiedExcerpt] = useState(false);

  useEffect(() => {
    if (citation) {
      previousFocusRef.current = document.activeElement as HTMLElement | null;
      const timer = setTimeout(() => {
        closeButtonRef.current?.focus();
      }, 25);
      return () => clearTimeout(timer);
    } else if (previousFocusRef.current) {
      previousFocusRef.current.focus();
    }
  }, [citation]);

  useEffect(() => {
    if (!citation) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [citation, onClose]);

  if (!citation) return null;

  const handleCopyExcerpt = () => {
    navigator.clipboard.writeText(citation.excerpt);
    setCopiedExcerpt(true);
    setTimeout(() => setCopiedExcerpt(false), 2000);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-xs"
      role="dialog"
      aria-modal="true"
      aria-labelledby="evidence-drawer-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-xl bg-[#111519] border-l border-[#262F38] h-full flex flex-col justify-between shadow-[0_0_64px_rgba(0,0,0,0.9)] overflow-hidden">
        {/* Drawer Header */}
        <div className="p-6 border-b border-[#1F262E] flex items-start justify-between gap-4 bg-[#0B0D0F]/60">
          <div className="space-y-1.5 min-w-0">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md bg-[#C6F36A]/10 border border-[#C6F36A]/30 text-[#C6F36A] text-[11px] font-mono">
              <ShieldCheck className="w-3.5 h-3.5" />
              Verified Policy Evidence
            </div>
            <h3
              id="evidence-drawer-title"
              className="text-lg font-semibold text-[#F3F5F7] leading-snug break-words"
            >
              {citation.title}
            </h3>
            <p className="text-xs font-mono text-[#9BA5B0]">
              Section: {citation.section || "Primary Clause"}
            </p>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Close evidence inspector"
            className="p-2 rounded-lg border border-[#262F38] bg-[#171C21] text-[#9BA5B0] hover:text-[#F3F5F7] hover:border-[#333F4C] transition shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Drawer Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Highlighted Verbatim Excerpt */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-[#9BA5B0] flex items-center gap-1.5">
                <BookOpen className="w-3.5 h-3.5 text-[#C6F36A]" />
                Cited Verbatim Excerpt
              </span>
              <button
                type="button"
                onClick={handleCopyExcerpt}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-[#262F38] bg-[#171C21] hover:bg-[#1D242B] text-[11px] font-medium text-[#F3F5F7] transition"
              >
                {copiedExcerpt ? (
                  <>
                    <Check className="w-3 h-3 text-[#2DD4BF]" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3 text-[#9BA5B0]" />
                    Copy Passage
                  </>
                )}
              </button>
            </div>

            <div className="relative rounded-xl border border-[#C6F36A]/35 bg-[#171C21] p-5 shadow-inner">
              <div className="absolute left-0 top-3 bottom-3 w-1 rounded-r bg-[#C6F36A]" />
              <blockquote className="pl-3 text-sm text-[#F3F5F7] leading-relaxed whitespace-pre-wrap font-sans">
                &ldquo;{citation.excerpt}&rdquo;
              </blockquote>
            </div>
          </div>

          {/* Provenance & Retrieval Telemetry */}
          <div className="space-y-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#9BA5B0] flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-[#60A5FA]" />
              Source Provenance & Retrieval Metadata
            </span>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {citation.score != null && (
                <div className="p-3.5 rounded-xl border border-[#1F262E] bg-[#171C21]/70">
                  <span className="text-[11px] text-[#6E7A87] block">
                    Retrieval / Grounding Score
                  </span>
                  <span className="text-sm font-mono font-semibold text-[#C6F36A] tabular-nums mt-0.5 block">
                    {citation.score.toFixed(4)}
                  </span>
                </div>
              )}

              {citation.page != null && (
                <div className="p-3.5 rounded-xl border border-[#1F262E] bg-[#171C21]/70">
                  <span className="text-[11px] text-[#6E7A87] block">
                    Source Page Number
                  </span>
                  <span className="text-sm font-mono font-semibold text-[#F3F5F7] tabular-nums mt-0.5 block">
                    Page #{citation.page}
                  </span>
                </div>
              )}

              {citation.sourceId && (
                <div className="p-3.5 rounded-xl border border-[#1F262E] bg-[#171C21]/70">
                  <span className="text-[11px] text-[#6E7A87] block">
                    Regulatory / Rule ID
                  </span>
                  <span className="text-xs font-mono text-[#F3F5F7] mt-0.5 block break-all">
                    {citation.sourceId}
                  </span>
                </div>
              )}

              {citation.documentId && (
                <div className="p-3.5 rounded-xl border border-[#1F262E] bg-[#171C21]/70">
                  <span className="text-[11px] text-[#6E7A87] block">
                    Document UUID
                  </span>
                  <span className="text-xs font-mono text-[#9BA5B0] mt-0.5 block break-all">
                    {citation.documentId}
                  </span>
                </div>
              )}

              {citation.chunkId && (
                <div className="p-3.5 rounded-xl border border-[#1F262E] bg-[#171C21]/70 sm:col-span-2">
                  <span className="text-[11px] text-[#6E7A87] block">
                    Indexed Chunk Identifier
                  </span>
                  <span className="text-xs font-mono text-[#9BA5B0] mt-0.5 block break-all">
                    {citation.chunkId}
                  </span>
                </div>
              )}
            </div>

            {citation.sourceUrl && (
              <div className="p-3.5 rounded-xl border border-[#1F262E] bg-[#171C21]/70 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="w-4 h-4 text-[#60A5FA] shrink-0" />
                  <span className="text-xs font-mono text-[#9BA5B0] truncate">
                    {citation.sourceUrl}
                  </span>
                </div>
                <a
                  href={citation.sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-medium text-[#C6F36A] hover:underline shrink-0"
                >
                  Open Reference
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            )}
          </div>

          <div className="p-4 rounded-xl border border-[#1F262E] bg-[#0B0D0F] text-xs text-[#9BA5B0] leading-relaxed">
            <strong className="text-[#F3F5F7]">Verification Notice:</strong> PayGuard AI
            cites only retrieved passages stored in the authorized pgvector index. Always
            verify that the excerpt above directly supports the operational decision before
            executing settlement or dispute actions.
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="p-4 border-t border-[#1F262E] bg-[#0B0D0F]/80 flex items-center justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-[#171C21] hover:bg-[#1D242B] border border-[#262F38] text-xs font-semibold text-[#F3F5F7] transition"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
}
