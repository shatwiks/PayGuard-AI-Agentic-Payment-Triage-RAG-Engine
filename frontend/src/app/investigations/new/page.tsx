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
  const [error, setError] = useState<{ message: string; code?: string; retryAfter?: number | null } | null>(null);

  // Quick payment preview verification
  const [verifyingPayment, setVerifyingPayment] = useState(false);
  const [verifiedPayment, setVerifiedPayment] = useState<PaymentDetail | null>(null);
  const [paymentVerifyError, setPaymentVerifyError] = useState<string | null>(null);

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
    } catch {
      setVerifiedPayment(null);
      setPaymentVerifyError("No payment found matching this reference.");
    } finally {
      setVerifyingPayment(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedQuery = customerQuery.trim();
    if (trimmedQuery.length < 5) {
      setError({ message: "Please enter a descriptive issue query of at least 5 characters." });
      return;
    }

    setIsSubmitting(true);
    try {
      const resultCase = await api.createInvestigation({
        customer_query: trimmedQuery,
        payment_reference: paymentReference.trim() || undefined,
        priority,
      });

      // Navigate to the created investigation result
      router.push(`/investigations/${resultCase.id}`);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError({
          message: err.message,
          code: err.code,
          retryAfter: err.retryAfter,
        });
      } else {
        setError({
          message: "Failed to initiate automated investigation. Please try again.",
        });
      }
    } finally {
      setIsSubmitting(false);
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
          className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-slate-800 mb-2"
        >
          <ArrowLeft className="w-3.5 h-3.5 mr-1" />
          Back to Investigations
        </Link>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">New Payment Investigation</h1>
        <p className="text-sm text-slate-500 mt-1">
          Provide the transaction reference and describe the customer problem for automated triage and policy RAG retrieval.
        </p>
      </div>

      {error && (
        <ErrorAlert
          message={error.message}
          code={error.code}
          retryAfter={error.retryAfter}
        />
      )}

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Form */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-6 shadow-2xs">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Payment Reference with Preview */}
            <div>
              <div className="flex items-center justify-between">
                <label
                  htmlFor="paymentRef"
                  className="block text-sm font-medium text-slate-800"
                >
                  Payment Reference Code
                </label>
                <span className="text-xs text-slate-400">Optional for general policy inquiries</span>
              </div>
              <div className="mt-1 flex rounded-lg shadow-2xs">
                <input
                  id="paymentRef"
                  type="text"
                  placeholder="e.g. tx_20261020_0001"
                  value={paymentReference}
                  onChange={(e) => setPaymentReference(e.target.value)}
                  onBlur={() => verifyReference(paymentReference)}
                  className="flex-1 min-w-0 px-3 py-2 border border-slate-300 rounded-l-lg text-sm font-mono placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => verifyReference(paymentReference)}
                  disabled={verifyingPayment || !paymentReference.trim()}
                  className="inline-flex items-center px-4 py-2 border border-l-0 border-slate-300 rounded-r-lg bg-slate-50 text-slate-700 hover:bg-slate-100 text-xs font-medium disabled:opacity-50"
                >
                  {verifyingPayment ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <>
                      <Search className="w-3.5 h-3.5 mr-1" />
                      Verify
                    </>
                  )}
                </button>
              </div>

              {/* Verified payment confirmation badge */}
              {verifiedPayment && (
                <div className="mt-2 p-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span className="font-medium text-emerald-900">
                      Found {verifiedPayment.currency} {Number(verifiedPayment.amount).toFixed(2)} via {verifiedPayment.gateway_name}
                    </span>
                  </div>
                  <StatusBadge status={verifiedPayment.status} type="payment" />
                </div>
              )}

              {paymentVerifyError && (
                <p className="mt-1.5 text-xs text-rose-600 flex items-center">
                  <AlertCircle className="w-3.5 h-3.5 mr-1" />
                  {paymentVerifyError}
                </p>
              )}
            </div>

            {/* Customer Query */}
            <div>
              <div className="flex items-center justify-between">
                <label
                  htmlFor="customerQuery"
                  className="block text-sm font-medium text-slate-800"
                >
                  Describe the Issue <span className="text-rose-500">*</span>
                </label>
                <span className="text-xs text-slate-400">
                  {customerQuery.length} / 4000 characters
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5 mb-2">
                Explain the customer dispute, failure notification, or refund inquiry in natural language.
              </p>
              <textarea
                id="customerQuery"
                rows={5}
                required
                maxLength={4000}
                placeholder="Example: Customer states their card was debited $150.00 but merchant terminal displayed 'transaction declined - code 51'. They request immediate credit or proof of settlement."
                value={customerQuery}
                onChange={(e) => setCustomerQuery(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* Case Priority */}
            <div>
              <label
                htmlFor="priority"
                className="block text-sm font-medium text-slate-800"
              >
                Case Priority
              </label>
              <div className="mt-1 grid grid-cols-2 sm:grid-cols-4 gap-2">
                {(["low", "medium", "high", "urgent"] as PriorityLevel[]).map((lvl) => (
                  <button
                    key={lvl}
                    type="button"
                    onClick={() => setPriority(lvl)}
                    className={`py-2 px-3 border rounded-lg text-xs font-medium capitalize text-center transition ${
                      priority === lvl
                        ? "border-blue-600 bg-blue-50 text-blue-700 shadow-2xs"
                        : "border-slate-200 hover:bg-slate-50 text-slate-700"
                    }`}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            {/* Form Action Buttons */}
            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
              <button
                type="button"
                onClick={handleReset}
                disabled={isSubmitting}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800"
              >
                Clear Form
              </button>

              <button
                type="submit"
                disabled={isSubmitting || customerQuery.trim().length < 5}
                className="inline-flex items-center px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm rounded-lg shadow-xs disabled:opacity-50 transition"
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

        {/* Right Column: Guidance Panel */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs">
            <h2 className="text-sm font-semibold text-slate-900 mb-2 flex items-center">
              <HelpCircle className="w-4 h-4 mr-1.5 text-blue-600" />
              What happens next?
            </h2>
            <p className="text-xs text-slate-500 mb-4">
              PayGuard AI executes a deterministic, multi-stage investigation workflow:
            </p>

            <ol className="relative pl-5 space-y-4 text-xs text-slate-600 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
              <li className="relative">
                <span className="absolute -left-5 mt-0.5 w-2 h-2 rounded-full bg-blue-600" />
                <strong className="text-slate-900">1. Parameterized Telemetry:</strong> Retrieves verified payment and processor gateway webhook logs.
              </li>
              <li className="relative">
                <span className="absolute -left-5 mt-0.5 w-2 h-2 rounded-full bg-blue-600" />
                <strong className="text-slate-900">2. Deterministic Triage:</strong> Evaluates payment status, gateway error codes, and intent keywords.
              </li>
              <li className="relative">
                <span className="absolute -left-5 mt-0.5 w-2 h-2 rounded-full bg-blue-600" />
                <strong className="text-slate-900">3. Hybrid Policy RAG:</strong> Searches official scheme rules and SOP policies via pgvector + FTS.
              </li>
              <li className="relative">
                <span className="absolute -left-5 mt-0.5 w-2 h-2 rounded-full bg-blue-600" />
                <strong className="text-slate-900">4. Grounded Synthesis:</strong> Synthesizes root-cause explanation backed strictly by verified citations.
              </li>
              <li className="relative">
                <span className="absolute -left-5 mt-0.5 w-2 h-2 rounded-full bg-blue-600" />
                <strong className="text-slate-900">5. Actionable Guidance:</strong> Prescribes concrete next steps (VOID_HOLD, REFUND, ESCALATE).
              </li>
            </ol>

            <div className="mt-5 p-3 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-500 leading-relaxed">
              <strong>Audit Notice:</strong> All customer queries undergo strict prompt sanitization and PII masking. Investigations are persisted with cryptographic audit trails.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function NewInvestigationPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-slate-500">Loading investigation form...</div>}>
      <NewInvestigationForm />
    </Suspense>
  );
}
