"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CreditCard,
  Calendar,
  AlertOctagon,
  ShieldAlert,
  Clock,
  Layers,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { PaymentDetail, PaymentEvent } from "@/lib/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ErrorAlert } from "@/components/ui/ErrorAlert";
import { CardSkeleton } from "@/components/ui/LoadingSkeleton";

export default function PaymentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const paymentId = resolvedParams.id;

  const [payment, setPayment] = useState<PaymentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code?: string; retryAfter?: number | null } | null>(null);
  const [expandedPayloads, setExpandedPayloads] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setLoading(true);
    setError(null);

    // Support either UUID or payment_reference
    const fetchPromise = paymentId.includes("-") && paymentId.length === 36
      ? api.getPayment(paymentId)
      : api.getPaymentByReference(paymentId);

    fetchPromise
      .then((data) => setPayment(data))
      .catch((err: any) => {
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

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-6 w-32 bg-slate-200 animate-pulse rounded" />
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
          className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-slate-800"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back to Payments
        </Link>
        <ErrorAlert
          message={error?.message || "Payment transaction could not be located."}
          code={error?.code}
          retryAfter={error?.retryAfter}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <Link
            href="/payments"
            className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-slate-800 mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" />
            Back to Payments
          </Link>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 font-mono">
              {payment.payment_reference}
            </h1>
            <StatusBadge status={payment.status} type="payment" />
          </div>
          <p className="text-xs text-slate-500 mt-1 font-mono">Internal UUID: {payment.id}</p>
        </div>

        <Link
          href={`/investigations/new?ref=${encodeURIComponent(payment.payment_reference)}`}
          className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-xs transition"
        >
          <ShieldAlert className="w-4 h-4 mr-1.5" />
          Investigate Payment
        </Link>
      </div>

      {/* Payment Attributes Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs">
        <h2 className="text-sm font-semibold text-slate-900 mb-4 flex items-center">
          <CreditCard className="w-4 h-4 mr-2 text-blue-600" />
          Financial & Gateway Metadata
        </h2>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
          <div>
            <span className="text-xs text-slate-500 block">Total Amount</span>
            <span className="text-xl font-bold text-slate-900 mt-0.5 block">
              {payment.currency} {Number(payment.amount).toFixed(2)}
            </span>
          </div>

          <div>
            <span className="text-xs text-slate-500 block">Payment Rail</span>
            <span className="text-sm font-semibold text-slate-800 mt-1 block capitalize">
              {payment.payment_method.replace("_", " ")}
            </span>
          </div>

          <div>
            <span className="text-xs text-slate-500 block">Processor Gateway</span>
            <span className="text-sm font-semibold text-slate-800 mt-1 block capitalize">
              {payment.gateway_name}
            </span>
          </div>

          <div>
            <span className="text-xs text-slate-500 block">Customer ID</span>
            <span className="text-sm font-mono text-slate-800 mt-1 block">
              {payment.customer_id}
            </span>
          </div>

          <div>
            <span className="text-xs text-slate-500 block">Merchant ID</span>
            <span className="text-sm font-mono text-slate-800 mt-1 block">
              {payment.merchant_id}
            </span>
          </div>

          <div>
            <span className="text-xs text-slate-500 block">Gateway Tx ID</span>
            <span className="text-sm font-mono text-slate-800 mt-1 block">
              {payment.gateway_transaction_id || "—"}
            </span>
          </div>

          <div>
            <span className="text-xs text-slate-500 block">Created Timestamp</span>
            <span className="text-xs text-slate-700 mt-1 block">
              {new Date(payment.created_at).toLocaleString()}
            </span>
          </div>

          <div>
            <span className="text-xs text-slate-500 block">Last Updated</span>
            <span className="text-xs text-slate-700 mt-1 block">
              {new Date(payment.updated_at).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Failure details if present */}
        {(payment.failure_code || payment.failure_message) && (
          <div className="mt-6 p-4 rounded-lg bg-rose-50 border border-rose-200">
            <div className="flex items-start">
              <AlertOctagon className="w-5 h-5 text-rose-600 mr-2 shrink-0 mt-0.5" />
              <div>
                <h4 className="text-xs font-bold text-rose-950 uppercase tracking-wider font-mono">
                  Gateway Error: {payment.failure_code || "FAILED"}
                </h4>
                <p className="text-sm text-rose-800 mt-1">
                  {payment.failure_message || "Processor rejected the transaction."}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Chronological Event History Timeline */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-2xs">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-900 flex items-center">
            <Clock className="w-4 h-4 mr-2 text-slate-600" />
            Chronological State Transition Timeline
          </h2>
          <span className="text-xs text-slate-500 font-mono">
            {payment.events.length} recorded events
          </span>
        </div>

        {payment.events.length === 0 ? (
          <p className="text-xs text-slate-400 italic py-4">No webhook telemetry events recorded.</p>
        ) : (
          <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
            {payment.events.map((evt) => {
              const isExpanded = !!expandedPayloads[evt.id];
              return (
                <div key={evt.id} className="relative group">
                  <div className="absolute -left-6 mt-1.5 w-3 h-3 rounded-full border-2 border-white bg-blue-600 shadow-xs" />
                  <div className="bg-slate-50/70 border border-slate-200 rounded-lg p-4">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-xs font-semibold text-slate-900">
                          {evt.event_type}
                        </span>
                        <div className="flex items-center text-xs text-slate-500">
                          {evt.from_status && (
                            <>
                              <span className="font-mono">{evt.from_status}</span>
                              <span className="mx-1 text-slate-400">&rarr;</span>
                            </>
                          )}
                          <span className="font-mono font-medium text-slate-800">{evt.to_status}</span>
                        </div>
                      </div>
                      <span className="text-xs text-slate-500">
                        {new Date(evt.occurred_at).toLocaleString()}
                      </span>
                    </div>

                    {/* Raw Payload Inspector Toggle */}
                    {evt.raw_payload && Object.keys(evt.raw_payload).length > 0 && (
                      <div className="mt-3 pt-2 border-t border-slate-200/60">
                        <button
                          onClick={() => togglePayload(evt.id)}
                          className="flex items-center text-xs text-slate-600 hover:text-slate-900 font-medium"
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
                          <pre className="mt-2 p-3 bg-slate-900 text-slate-200 rounded-md text-xs font-mono overflow-x-auto max-h-60">
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
  );
}
