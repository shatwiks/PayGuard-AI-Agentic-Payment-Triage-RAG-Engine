"use client";

import React from "react";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, ShieldAlert } from "lucide-react";

export default function PrivacyNoticePage() {
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
                This route is a non-binding technical placeholder. Finalized privacy policy terms must be drafted and approved by your organization&apos;s legal and data protection counsel prior to external production deployment.
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center gap-2.5">
              <ShieldAlert className="w-5 h-5 text-[#C6F36A]" />
              <h1 className="text-2xl font-bold text-[#F3F5F7]">
                Technical Data Handling Summary (Codebase Facts)
              </h1>
            </div>
            <p className="text-sm text-[#9BA5B0] leading-relaxed">
              While formal legal terms are pending review, the following technical data-handling behaviors are implemented in the PayGuard AI repository:
            </p>
            <ul className="space-y-3 text-xs text-[#F3F5F7]/90 list-disc pl-5 leading-relaxed">
              <li>
                <strong>Query Sanitization & PII Masking:</strong> Customer dispute queries submitted to{" "}
                <code className="font-mono text-[#C6F36A]">POST /api/v1/investigations</code>{" "}
                undergo prompt sanitization and configurable PII masking before persistence and LLM reasoning.
              </li>
              <li>
                <strong>Tenant Document Isolation:</strong> Compliance documents uploaded via{" "}
                <code className="font-mono text-[#C6F36A]">POST /api/v1/knowledge/upload</code>{" "}
                are scoped to the authenticated uploader&apos;s user ID (<code className="font-mono">uploaded_by_id</code>).
              </li>
              <li>
                <strong>Authentication Storage:</strong> Operator session tokens are stored in browser{" "}
                <code className="font-mono">localStorage</code> under{" "}
                <code className="font-mono">payguard_access_token</code> and cleared upon sign-out or HTTP 401 responses.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
