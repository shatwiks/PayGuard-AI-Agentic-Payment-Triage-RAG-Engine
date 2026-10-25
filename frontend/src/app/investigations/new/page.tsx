"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ShieldAlert,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Loader2,
  Search,
  Clock,
  GitCommit,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { PaymentDetail, PriorityLevel } from "@/lib/types";
import { ErrorAlert } from "@/components/ui/ErrorAlert";
import { StatusBadge } from "@/components/ui/StatusBadge";

function NewInvestigationForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialRef = searchParams.get("ref") || "";

  const [paymentReference, setPaymentReference] = useState(initialRef);
  const [customerQuery, setCustomerQuery] = useState("");
  const [priority, setPriority] = useState<PriorityLevel>("medium");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<{
    message: string;
    code?: string;
    retryAfter?: number | null;
  } | null>(null);

  // Quick payment preview verification
  const [verifyingPayment, setVerifyingPayment] = useState(false);
  const [verifiedPayment, setVerifiedPayment] = useState<PaymentDetail | null>(
    null
  );
  const [paymentVerifyError, setPaymentVerifyError] = useState<string | null>(
    null
  );

  useEffect(() => {
    if (initialRef) {
      verifyReference(initialRef);
    }
  }, [initialRef]);

  const verifyReference = async (ref: string) => {
    const trimmed = ref.trim();
    if (!trimmed) {
      setVerifiedPayment(null);
      setPaymentVerifyError(null);
      return;
    }
    setVerifyingPayment(true);
    setPaymentVerifyError(null);
    try {
      const p = await api.getPaymentByReference(trimmed);
      setVerifiedPayment(p);
    } catch (err: any) {
      setVerifiedPayment(null);
      if (err instanceof ApiError && err.code === "TIMEOUT") {
        setPaymentVerifyError(
          "Verification request timed out. This does not indicate the payment failed—please retry."
        );
      } else {
        setPaymentVerifyError("No payment found matching this reference.");
      }
    } finally {
      setVerifyingPayment(false);
    }
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (isSubmitting) return;
    setError(null);

    const trimmedQuery = customerQuery.trim();
    if (trimmedQuery.length < 5) {
      setError({
        message:
          "Please enter a descriptive issue query of at least 5 characters.",
      });
      return;
    }

    setIsSubmitting(true);
    try {
      const resultCase = await api.createInvestigation({
        customer_query: trimmedQuery,
        payment_reference: paymentReference.trim() || undefined,
        priority,
      });

      router.push(`/investigations/${resultCase.id}`);
    } catch (err: any) {
      if (err instanceof ApiError) {
        const message =
          err.code === "TIMEOUT"
            ? "The investigation request timed out waiting for the server. A timeout is not proof of payment failure or investigation failure—please retry or inspect the Investigations list."
            : err.message;
        setError({
          message,
          code: err.code,
          retryAfter: err.retryAfter,
        });
      } else {
        setError({
          message:
            "Failed to initiate automated investigation. Please try again.",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleReset = () => {
    setPaymentReference("");
    setCustomerQuery("");
    setPriority("medium");
    setVerifiedPayment(null);
    setPaymentVerifyError(null);
    setError(null);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          href="/investigations"
          className="inline-flex items-center text-xs font-medium text-[#9BA5B0] hover:text-[#F3F5F7] mb-2 transition"
        >
          <ArrowLeft className="w-3.5 h-3.5 mr-1" />
          Back to Investigations
        </Link>
        <h1 className="text-2xl font-bold tracking-tight text-[#F3F5F7]">
          New Payment Investigation
        </h1>
        <p className="text-xs sm:text-sm text-[#9BA5B0] mt-1">
          Provide the transaction reference and describe the customer problem for deterministic triage and policy RAG retrieval.
        </p>
      </div>

      {error && (
        <ErrorAlert
          message={error.message}
          code={error.code}
          retryAfter={error.retryAfter}
          onRetry={() => handleSubmit()}
        />
      )}

      {/* Two Column Workspace Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Investigation Submission Form (7 Cols) */}
        <div className="lg:col-span-7 bg-[#111519] rounded-xl border border-[#1F262E] p-6">
          <form onSubmit={handleSubmit} className="space-y-6" noValidate>
            {/* Payment Reference with Live Verification */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label
                  htmlFor="paymentRef"
                  className="block text-xs font-semibold text-[#F3F5F7]"
                >
                  Payment Reference Code
                </label>
                <span className="text-[11px] font-mono text-[#6E7A87]">
                  Optional for general policy inquiries
                </span>
              </div>
              <div className="flex rounded-xl overflow-hidden border border-[#262F38] focus-within:border-[#C6F36A] transition">
                <input
                  id="paymentRef"
                  type="text"
                  placeholder="e.g. tx_20261020_0001"
                  value={paymentReference}
                  onChange={(e) => setPaymentReference(e.target.value)}
                  onBlur={() => verifyReference(paymentReference)}
                  className="flex-1 min-w-0 px-3.5 py-2.5 bg-[#0B0D0F] text-sm font-mono text-[#F3F5F7] placeholder-[#6E7A87] focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => verifyReference(paymentReference)}
                  disabled={verifyingPayment || !paymentReference.trim()}
                  className="inline-flex items-center px-4 py-2 bg-[#171C21] hover:bg-[#1D242B] text-[#C6F36A] border-l border-[#262F38] text-xs font-mono font-semibold disabled:opacity-40 transition"
                >
                  {verifyingPayment ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <>
                      <Search className="w-3.5 h-3.5 mr-1.5" />
                      Verify
                    </>
                  )}
                </button>
              </div>

              {/* Verified Payment Confirmation Badge */}
              {verifiedPayment && (
                <div className="mt-3 p-3.5 bg-[#2DD4BF]/10 border border-[#2DD4BF]/30 rounded-xl flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-[#2DD4BF] shrink-0" />
                    <span className="font-mono font-semibold text-[#F3F5F7] tabular-nums">
                      Found {verifiedPayment.currency}{" "}
                      {Number(verifiedPayment.amount).toFixed(2)} via{" "}
                      {verifiedPayment.gateway_name}
                    </span>
                  </div>
                  <StatusBadge status={verifiedPayment.status} type="payment" />
                </div>
              )}

              {paymentVerifyError && (
                <p className="mt-2 text-xs text-[#F87171] flex items-center font-mono">
                  <AlertCircle className="w-3.5 h-3.5 mr-1.5 shrink-0" />
                  {paymentVerifyError}
                </p>
              )}
            </div>

            {/* Customer Query */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label
                  htmlFor="customerQuery"
                  className="block text-xs font-semibold text-[#F3F5F7]"
                >
                  Describe the Issue <span className="text-[#F87171]">*</span>
                </label>
                <span className="text-[11px] font-mono text-[#6E7A87] tabular-nums">
                  {customerQuery.length} / 4000 chars
                </span>
              </div>
              <p className="text-xs text-[#9BA5B0] mb-2">
                Explain the customer dispute, gateway failure notification, or refund inquiry. Press Ctrl+Enter to submit.
              </p>
              <textarea
                id="customerQuery"
                rows={5}
                required
                maxLength={4000}
                placeholder="Example: Customer states their card was debited $150.00 but merchant terminal displayed 'transaction declined - code 51'. They request immediate credit or proof of settlement."
                value={customerQuery}
                onChange={(e) => setCustomerQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full px-3.5 py-2.5 bg-[#0B0D0F] border border-[#262F38] focus:border-[#C6F36A] rounded-xl text-sm text-[#F3F5F7] placeholder-[#6E7A87] focus:outline-none transition leading-relaxed"
              />
            </div>

            {/* Case Priority */}
            <div>
              <label className="block text-xs font-semibold text-[#F3F5F7] mb-2">
                Case Priority
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {(["low", "medium", "high", "urgent"] as PriorityLevel[]).map(
                  (lvl) => (
                    <button
                      key={lvl}
                      type="button"
                      onClick={() => setPriority(lvl)}
                      className={`py-2.5 px-3 border rounded-xl text-xs font-mono font-semibold capitalize text-center transition ${
                        priority === lvl
                          ? "border-[#C6F36A] bg-[#C6F36A]/10 text-[#C6F36A]"
                          : "border-[#262F38] bg-[#0B0D0F] hover:bg-[#171C21] text-[#9BA5B0]"
                      }`}
                    >
                      {lvl}
                    </button>
                  )
                )}
              </div>
            </div>

            {/* Form Action Buttons */}
            <div className="pt-4 border-t border-[#1F262E] flex items-center justify-between">
              <button
                type="button"
                onClick={handleReset}
                disabled={isSubmitting}
                className="px-4 py-2 text-xs font-medium text-[#9BA5B0] hover:text-[#F3F5F7] transition"
              >
                Clear Form
              </button>

              <button
                type="submit"
                disabled={isSubmitting || customerQuery.trim().length < 5}
                className="inline-flex items-center px-5 py-2.5 bg-[#C6F36A] hover:bg-[#D4F788] text-[#0B0D0F] font-semibold text-xs rounded-xl disabled:opacity-40 transition active:scale-[0.98]"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Running Autonomous Triage...
                  </>
                ) : (
                  <>
                    <ShieldAlert className="w-4 h-4 mr-1.5" />
                    Start Investigation
                  </>
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Right Column: Live Payment Preview (if verified) + Pipeline Guidance (5 Cols) */}
        <div className="lg:col-span-5 space-y-6">
          {verifiedPayment && (
            <div className="bg-[#111519] rounded-xl border border-[#262F38] p-5 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-[#1F262E]">
                <div>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[#2DD4BF] block">
                    Confirmed Ledger Telemetry
                  </span>
                  <h2 className="text-sm font-mono font-bold text-[#F3F5F7]">
                    {verifiedPayment.payment_reference}
                  </h2>
                </div>
                <Link
                  href={`/payments/${verifiedPayment.id}`}
                  className="text-xs font-mono text-[#C6F36A] hover:underline"
                >
                  Full Ledger &rarr;
                </Link>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="p-2.5 rounded-lg bg-[#0B0D0F] border border-[#1F262E]">
                  <span className="text-[10px] text-[#6E7A87] block">AMOUNT</span>
                  <span className="text-[#F3F5F7] font-semibold tabular-nums">
                    {verifiedPayment.currency}{" "}
                    {Number(verifiedPayment.amount).toFixed(2)}
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-[#0B0D0F] border border-[#1F262E]">
                  <span className="text-[10px] text-[#6E7A87] block">RAIL</span>
                  <span className="text-[#F3F5F7] capitalize">
                    {verifiedPayment.payment_method.replace(/_/g, " ")}
                  </span>
                </div>
              </div>

              {verifiedPayment.events && verifiedPayment.events.length > 0 && (
                <div className="space-y-2">
                  <span className="text-[11px] font-mono text-[#9BA5B0] flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-[#C6F36A]" />
                    Recorded Webhook Events ({verifiedPayment.events.length})
                  </span>
                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {verifiedPayment.events.map((evt) => (
                      <div
                        key={evt.id}
                        className="p-2.5 rounded-lg bg-[#0B0D0F] border border-[#1F262E] text-xs font-mono flex items-center justify-between gap-2"
                      >
                        <div className="flex items-center gap-1.5 truncate">
                          <GitCommit className="w-3 h-3 text-[#C6F36A] shrink-0" />
                          <span className="text-[#F3F5F7] truncate">
                            {evt.event_type}
                          </span>
                        </div>
                        <span className="text-[11px] text-[#9BA5B0] shrink-0">
                          &rarr; {evt.to_status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="bg-[#111519] rounded-xl border border-[#1F262E] p-5">
            <h2 className="text-sm font-semibold text-[#F3F5F7] mb-2 flex items-center">
              <HelpCircle className="w-4 h-4 mr-1.5 text-[#C6F36A]" />
              Investigation Execution Pipeline
            </h2>
            <p className="text-xs text-[#9BA5B0] mb-4">
              PayGuard AI executes a deterministic, multi-stage investigation workflow:
            </p>

            <ol className="relative pl-5 space-y-4 text-xs text-[#9BA5B0] before:absolute before:left-2 before:top-2 before:bottom-2 before:w-px before:bg-[#262F38]">
              <li className="relative">
                <span className="absolute -left-[15px] mt-1 w-2 h-2 rounded-full bg-[#C6F36A]" />
                <strong className="text-[#F3F5F7]">
                  1. Parameterized Telemetry:
                </strong>{" "}
                Retrieves verified payment and processor gateway webhook logs.
              </li>
              <li className="relative">
                <span className="absolute -left-[15px] mt-1 w-2 h-2 rounded-full bg-[#C6F36A]" />
                <strong className="text-[#F3F5F7]">
                  2. Deterministic Triage:
                </strong>{" "}
                Evaluates payment status, gateway error codes, and intent keywords.
              </li>
              <li className="relative">
                <span className="absolute -left-[15px] mt-1 w-2 h-2 rounded-full bg-[#C6F36A]" />
                <strong className="text-[#F3F5F7]">3. Hybrid Policy RAG:</strong>{" "}
                Searches official scheme rules and SOP policies via pgvector + FTS.
              </li>
              <li className="relative">
                <span className="absolute -left-[15px] mt-1 w-2 h-2 rounded-full bg-[#C6F36A]" />
                <strong className="text-[#F3F5F7]">
                  4. Grounded Synthesis:
                </strong>{" "}
                Synthesizes root-cause explanation backed strictly by verified citations.
              </li>
              <li className="relative">
                <span className="absolute -left-[15px] mt-1 w-2 h-2 rounded-full bg-[#C6F36A]" />
                <strong className="text-[#F3F5F7]">
                  5. Actionable Guidance:
                </strong>{" "}
                Prescribes concrete next steps (VOID_HOLD, REFUND, ESCALATE).
              </li>
            </ol>

            <div className="mt-5 p-3.5 rounded-xl bg-[#0B0D0F] border border-[#1F262E] text-[11px] text-[#6E7A87] leading-relaxed">
              <strong className="text-[#9BA5B0]">Audit Notice:</strong> All customer queries undergo prompt sanitization and PII masking. Investigations are persisted with immutable evidence packages.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function NewInvestigationPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-xs font-mono text-[#9BA5B0]">
          Loading investigation workspace...
        </div>
      }
    >
      <NewInvestigationForm />
    </Suspense>
  );
}
