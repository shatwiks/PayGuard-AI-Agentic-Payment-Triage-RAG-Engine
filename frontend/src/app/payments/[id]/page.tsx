"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CreditCard,
  AlertOctagon,
  ShieldAlert,
  Clock,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { PaymentDetail } from "@/lib/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ErrorAlert } from "@/components/ui/ErrorAlert";
import { CardSkeleton } from "@/components/ui/LoadingSkeleton";
import { useToast } from "@/components/ui/ToastContext";

export default function PaymentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const paymentId = resolvedParams.id;
  const { addToast } = useToast();

  const [payment, setPayment] = useState<PaymentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{
    message: string;
    code?: string;
    retryAfter?: number | null;
  } | null>(null);
  const [expandedPayloads, setExpandedPayloads] = useState<
    Record<string, boolean>
  >({});
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);

    // Support either UUID or payment_reference
    const fetchPromise =
      paymentId.includes("-") && paymentId.length === 36
        ? api.getPayment(paymentId)
        : api.getPaymentByReference(paymentId);

    fetchPromise
      .then((data) => setPayment(data))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({
            message: err.message,
            code: err.code,
            retryAfter: err.retryAfter,
          });
        } else {
          setError({
            message: "Unable to retrieve payment transaction record.",
          });
        }
      })
      .finally(() => setLoading(false));
  }, [paymentId]);

  const togglePayload = (eventId: string) => {
    setExpandedPayloads((prev) => ({
      ...prev,
      [eventId]: !prev[eventId],
    }));
  };

  const handleCopyRef = async (ref: string) => {
    try {
      await navigator.clipboard.writeText(ref);
      setCopied(true);
      addToast(`Copied ${ref} to clipboard`, "success");
      setTimeout(() => setCopied(false), 1800);
    } catch {
      addToast("Unable to copy reference", "error");
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

  if (error || !payment) {
    return (
      <div className="space-y-4">
        <Link
          href="/payments"
          className="inline-flex items-center text-xs font-medium text-[#9BA5B0] hover:text-[#F3F5F7] transition"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          Back to Payments
        </Link>
        <ErrorAlert
          message={
            error?.message || "Payment transaction could not be located."
          }
          code={error?.code}
          retryAfter={error?.retryAfter}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#1F262E]">
        <div>
          <Link
            href="/payments"
            className="inline-flex items-center text-xs font-medium text-[#9BA5B0] hover:text-[#F3F5F7] mb-2 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
            Back to Payments
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-[#F3F5F7] font-mono tabular-nums">
              {payment.payment_reference}
            </h1>
            <StatusBadge status={payment.status} type="payment" />
            <button
              type="button"
              onClick={() => handleCopyRef(payment.payment_reference)}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#111519] border border-[#262F38] text-xs font-mono text-[#9BA5B0] hover:text-[#F3F5F7] transition"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-[#2DD4BF]" />
                  <span>Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Copy Ref</span>
                </>
              )}
            </button>
          </div>
          <p className="text-xs text-[#6E7A87] mt-1 font-mono tabular-nums">
            Internal UUID: {payment.id}
          </p>
        </div>

        <Link
          href={`/investigations/new?ref=${encodeURIComponent(payment.payment_reference)}`}
          className="inline-flex items-center px-4 py-2.5 text-xs font-semibold text-[#0B0D0F] bg-[#C6F36A] hover:bg-[#D4F788] rounded-xl transition active:scale-[0.98]"
        >
          <ShieldAlert className="w-4 h-4 mr-1.5" />
          Investigate Payment
        </Link>
      </div>

      {/* Payment Attributes Card */}
      <div className="pg-surface-shell">
        <div className="pg-surface-core p-6">
          <h2 className="text-sm font-semibold text-[#F3F5F7] mb-5 flex items-center">
            <CreditCard className="w-4 h-4 mr-2 text-[#C6F36A]" />
            Financial & Gateway Metadata
          </h2>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-5">
            <div className="p-3.5 rounded-xl bg-[#0B0D0F] border border-[#1F262E]">
              <span className="text-[11px] font-mono uppercase text-[#6E7A87] block">
                Total Amount
              </span>
              <span className="text-xl font-bold font-mono text-[#F3F5F7] tabular-nums mt-1 block">
                {payment.currency} {Number(payment.amount).toFixed(2)}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#0B0D0F] border border-[#1F262E]">
              <span className="text-[11px] font-mono uppercase text-[#6E7A87] block">
                Payment Rail
              </span>
              <span className="text-sm font-semibold text-[#F3F5F7] mt-1.5 block capitalize">
                {payment.payment_method.replace("_", " ")}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#0B0D0F] border border-[#1F262E]">
              <span className="text-[11px] font-mono uppercase text-[#6E7A87] block">
                Processor Gateway
              </span>
              <span className="text-sm font-semibold text-[#F3F5F7] mt-1.5 block capitalize">
                {payment.gateway_name}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#0B0D0F] border border-[#1F262E]">
              <span className="text-[11px] font-mono uppercase text-[#6E7A87] block">
                Customer ID
              </span>
              <span className="text-sm font-mono text-[#F3F5F7] tabular-nums mt-1.5 block">
                {payment.customer_id}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#0B0D0F] border border-[#1F262E]">
              <span className="text-[11px] font-mono uppercase text-[#6E7A87] block">
                Merchant ID
              </span>
              <span className="text-sm font-mono text-[#F3F5F7] tabular-nums mt-1.5 block">
                {payment.merchant_id}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#0B0D0F] border border-[#1F262E]">
              <span className="text-[11px] font-mono uppercase text-[#6E7A87] block">
                Gateway Tx ID
              </span>
              <span className="text-sm font-mono text-[#9BA5B0] tabular-nums mt-1.5 block">
                {payment.gateway_transaction_id || "—"}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#0B0D0F] border border-[#1F262E]">
              <span className="text-[11px] font-mono uppercase text-[#6E7A87] block">
                Created Timestamp
              </span>
              <span className="text-xs font-mono text-[#9BA5B0] tabular-nums mt-1.5 block">
                {new Date(payment.created_at).toLocaleString()}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#0B0D0F] border border-[#1F262E]">
              <span className="text-[11px] font-mono uppercase text-[#6E7A87] block">
                Last Updated
              </span>
              <span className="text-xs font-mono text-[#9BA5B0] tabular-nums mt-1.5 block">
                {new Date(payment.updated_at).toLocaleString()}
              </span>
            </div>
          </div>

          {/* Failure details if present */}
          {(payment.failure_code || payment.failure_message) && (
            <div className="mt-6 p-4 rounded-xl bg-[#F87171]/10 border border-[#F87171]/30">
              <div className="flex items-start gap-3">
                <AlertOctagon className="w-5 h-5 text-[#F87171] shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-xs font-bold text-[#F87171] uppercase tracking-wider font-mono">
                    Gateway Error: {payment.failure_code || "FAILED"}
                  </h3>
                  <p className="text-xs text-[#F3F5F7] mt-1">
                    {payment.failure_message ||
                      "Processor rejected the transaction."}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Chronological Event History Timeline */}
      <div className="pg-surface-shell">
        <div className="pg-surface-core p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-sm font-semibold text-[#F3F5F7] flex items-center">
              <Clock className="w-4 h-4 mr-2 text-[#C6F36A]" />
              Chronological State Transition Timeline
            </h2>
            <span className="text-xs text-[#9BA5B0] font-mono tabular-nums">
              {payment.events.length} recorded events
            </span>
          </div>

          {payment.events.length === 0 ? (
            <p className="text-xs text-[#6E7A87] italic py-4">
              No webhook telemetry events recorded.
            </p>
          ) : (
            <div className="relative pl-6 space-y-5 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-px before:bg-[#262F38]">
              {payment.events.map((evt) => {
                const isExpanded = !!expandedPayloads[evt.id];
                return (
                  <div key={evt.id} className="relative">
                    <div className="absolute -left-6 mt-1.5 w-3 h-3 rounded-full border-2 border-[#0B0D0F] bg-[#C6F36A]" />
                    <div className="bg-[#0B0D0F] border border-[#1F262E] rounded-xl p-4">
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2.5">
                          <span className="font-mono text-xs font-semibold text-[#F3F5F7]">
                            {evt.event_type}
                          </span>
                          <div className="flex items-center text-xs font-mono text-[#9BA5B0]">
                            {evt.from_status && (
                              <>
                                <span>{evt.from_status}</span>
                                <span className="mx-1.5 text-[#6E7A87]">&rarr;</span>
                              </>
                            )}
                            <span className="font-semibold text-[#C6F36A]">
                              {evt.to_status}
                            </span>
                          </div>
                        </div>
                        <span className="text-xs font-mono text-[#6E7A87] tabular-nums">
                          {new Date(evt.occurred_at).toLocaleString()}
                        </span>
                      </div>

                      {/* Raw Payload Inspector Toggle */}
                      {evt.raw_payload &&
                        Object.keys(evt.raw_payload).length > 0 && (
                          <div className="mt-3 pt-3 border-t border-[#1F262E]">
                            <button
                              type="button"
                              onClick={() => togglePayload(evt.id)}
                              className="flex items-center text-xs font-mono text-[#9BA5B0] hover:text-[#C6F36A] transition"
                            >
                              {isExpanded ? (
                                <>
                                  <ChevronUp className="w-3.5 h-3.5 mr-1" />
                                  Hide Raw Webhook Payload
                                </>
                              ) : (
                                <>
                                  <ChevronDown className="w-3.5 h-3.5 mr-1" />
                                  Inspect Raw Webhook Payload
                                </>
                              )}
                            </button>
                            {isExpanded && (
                              <pre className="mt-2.5 p-3.5 bg-[#111519] border border-[#262F38] text-[#9BA5B0] rounded-lg text-xs font-mono overflow-x-auto max-h-60">
                                {JSON.stringify(evt.raw_payload, null, 2)}
                              </pre>
                            )}
                          </div>
                        )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
