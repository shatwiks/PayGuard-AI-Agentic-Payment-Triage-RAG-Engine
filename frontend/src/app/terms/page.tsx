"use client";

import React from "react";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, ShieldAlert } from "lucide-react";

export default function TermsNoticePage() {
  return (
    <div className="min-h-[100dvh] bg-[#0B0D0F] text-[#F3F5F7] py-16 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto space-y-8">
        <div className="flex items-center justify-between">
          <Link
            href="/welcome"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-[#9BA5B0] hover:text-[#F3F5F7] transition"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to PayGuard AI</span>
          </Link>
          <span className="text-xs font-mono text-[#F59E0B] bg-[#F59E0B]/10 border border-[#F59E0B]/30 px-2.5 py-0.5 rounded">
            LEGAL REVIEW REQUIRED
          </span>
        </div>

        <div className="rounded-2xl border border-[#262F38] bg-[#111519] p-8 space-y-6">
          <div className="flex items-start gap-3.5 p-4 rounded-xl bg-[#F59E0B]/10 border border-[#F59E0B]/30">
            <AlertTriangle className="w-5 h-5 text-[#F59E0B] shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h2 className="text-sm font-semibold text-[#F3F5F7]">
                Placeholder Route — Organizational Legal Review Required
              </h2>
              <p className="text-xs text-[#9BA5B0] leading-relaxed">
                This route is a non-binding technical placeholder. Finalized Terms and Conditions must be reviewed and approved by qualified legal counsel before production use.
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center gap-2.5">
              <ShieldAlert className="w-5 h-5 text-[#C6F36A]" />
              <h1 className="text-2xl font-bold text-[#F3F5F7]">
                Operational Scope & Advisory Notice
              </h1>
            </div>
            <p className="text-sm text-[#9BA5B0] leading-relaxed">
              PayGuard AI is an investigative decision-support and retrieval-augmented generation (RAG) workspace:
            </p>
            <ul className="space-y-3 text-xs text-[#F3F5F7]/90 list-disc pl-5 leading-relaxed">
              <li>
                <strong>Decision-Support Only:</strong> Triage classifications, confidence scores, and AI-synthesized explanations are assistive tools for human operators and do not constitute binding legal or financial determinations.
              </li>
              <li>
                <strong>No Autonomous Financial Execution:</strong> The platform inspects transaction telemetry in read-only mode and does not initiate processor refunds, reversals, or ledger transfers.
              </li>
              <li>
                <strong>Human Review Requirement:</strong> Cases flagged with{" "}
                <code className="font-mono text-[#C6F36A]">human_review_required = true</code>{" "}
                require explicit analyst verification against primary processor records.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
