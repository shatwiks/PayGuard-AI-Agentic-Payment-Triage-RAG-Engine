"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Eye,
  Copy,
  Check,
  ShieldAlert,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { PaymentSummary } from "@/lib/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ErrorAlert } from "@/components/ui/ErrorAlert";
import { EmptyState } from "@/components/ui/EmptyState";
import { TableRowSkeleton } from "@/components/ui/LoadingSkeleton";
import { useToast } from "@/components/ui/ToastContext";

export default function PaymentsPage() {
  const { addToast } = useToast();
  const [payments, setPayments] = useState<PaymentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{
    message: string;
    code?: string;
    retryAfter?: number | null;
  } | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Filters
  const [referenceQuery, setReferenceQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [methodFilter, setMethodFilter] = useState("");
  const [gatewayFilter, setGatewayFilter] = useState("");

  const fetchPayments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listPayments({
        payment_reference: referenceQuery.trim() || undefined,
        status: statusFilter || undefined,
        payment_method: methodFilter || undefined,
        gateway_name: gatewayFilter || undefined,
        page,
        page_size: pageSize,
      });
      setPayments(res.items || []);
      setTotal(res.total || 0);
      setTotalPages(res.total_pages || 1);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError({
          message: err.message,
          code: err.code,
          retryAfter: err.retryAfter,
        });
      } else {
        setError({
          message: "Unable to retrieve payments from backend.",
        });
      }
    } finally {
      setLoading(false);
    }
  }, [
    referenceQuery,
    statusFilter,
    methodFilter,
    gatewayFilter,
    page,
    pageSize,
  ]);

  useEffect(() => {
    fetchPayments();
  }, [fetchPayments]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchPayments();
  };

  const handleResetFilters = () => {
    setReferenceQuery("");
    setStatusFilter("");
    setMethodFilter("");
    setGatewayFilter("");
    setPage(1);
  };

  const handleCopyRef = async (ref: string, id: string) => {
    try {
      await navigator.clipboard.writeText(ref);
      setCopiedId(id);
      addToast(`Copied ${ref}`, "success");
      setTimeout(() => setCopiedId(null), 1800);
    } catch {
      addToast("Failed to copy reference", "error");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <span className="text-[11px] font-mono uppercase tracking-widest text-[#C6F36A] block mb-1">
            Gateway Telemetry Ledger
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-[#F3F5F7]">
            Payment Transactions
          </h1>
          <p className="text-xs text-[#9BA5B0] mt-1">
            Search, filter, and inspect transaction telemetry across payment gateways.
          </p>
        </div>
        <div className="flex items-center space-x-2.5">
          <button
            type="button"
            onClick={() => fetchPayments()}
            className="inline-flex items-center px-3.5 py-2 border border-[#262F38] rounded-xl text-xs font-medium text-[#9BA5B0] bg-[#111519] hover:text-[#F3F5F7] hover:border-[#384654] transition active:scale-[0.98]"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin text-[#C6F36A]" : ""}`}
            />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <ErrorAlert
          message={error.message}
          code={error.code}
          retryAfter={error.retryAfter}
          onRetry={fetchPayments}
        />
      )}

      {/* Filter and Search Bar */}
      <div className="pg-surface-shell">
        <div className="pg-surface-core p-4">
          <form
            onSubmit={handleSearchSubmit}
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3"
          >
            <div className="lg:col-span-2 relative">
              <Search className="w-4 h-4 text-[#6E7A87] absolute left-3.5 top-2.5 pointer-events-none" />
              <input
                type="text"
                aria-label="Search by payment reference"
                placeholder="Search by payment reference (e.g. tx_...)"
                value={referenceQuery}
                onChange={(e) => setReferenceQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-xs font-mono text-[#F3F5F7] placeholder-[#6E7A87] focus:outline-none focus:border-[#C6F36A] transition"
              />
            </div>

            <div>
              <select
                aria-label="Filter by payment status"
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-2 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-xs text-[#F3F5F7] focus:outline-none focus:border-[#C6F36A] transition"
              >
                <option value="">All Statuses</option>
                <option value="captured">Captured</option>
                <option value="authorized">Authorized</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
                <option value="reversed">Reversed</option>
                <option value="refunded">Refunded</option>
                <option value="disputed">Disputed</option>
              </select>
            </div>

            <div>
              <select
                aria-label="Filter by payment rail"
                value={methodFilter}
                onChange={(e) => {
                  setMethodFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-2 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-xs text-[#F3F5F7] focus:outline-none focus:border-[#C6F36A] transition"
              >
                <option value="">All Payment Rails</option>
                <option value="credit_card">Credit Card</option>
                <option value="ach">ACH Transfer</option>
                <option value="upi">UPI</option>
                <option value="debit_card">Debit Card</option>
              </select>
            </div>

            <div className="flex space-x-2">
              <button
                type="submit"
                className="flex-1 px-4 py-2 bg-[#C6F36A] hover:bg-[#D4F788] text-[#0B0D0F] font-semibold text-xs rounded-xl transition active:scale-[0.98]"
              >
                Filter
              </button>
              {(referenceQuery ||
                statusFilter ||
                methodFilter ||
                gatewayFilter) && (
                <button
                  type="button"
                  onClick={handleResetFilters}
                  className="px-3 py-2 border border-[#262F38] bg-[#171C21] hover:text-[#F3F5F7] text-[#9BA5B0] rounded-xl text-xs font-medium transition"
                >
                  Reset
                </button>
              )}
            </div>
          </form>
        </div>
      </div>

      {/* Payments Table */}
      <div className="pg-surface-shell overflow-hidden">
        <div className="pg-surface-core overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#0B0D0F]/60 border-b border-[#1F262E] text-[11px] font-mono text-[#6E7A87] uppercase tracking-wider">
                  <th className="py-3.5 px-5">Payment Reference</th>
                  <th className="py-3.5 px-4">Customer ID</th>
                  <th className="py-3.5 px-4">Amount</th>
                  <th className="py-3.5 px-4">Payment Rail</th>
                  <th className="py-3.5 px-4">Gateway</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4">Created Time</th>
                  <th className="py-3.5 px-5 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1F262E] text-sm">
                {loading ? (
                  <>
                    <TableRowSkeleton columns={8} />
                    <TableRowSkeleton columns={8} />
                    <TableRowSkeleton columns={8} />
                    <TableRowSkeleton columns={8} />
                    <TableRowSkeleton columns={8} />
                  </>
                ) : payments.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 px-4">
                      <EmptyState
                        title="No payment records found"
                        description="Try adjusting your search criteria or filter options to locate transactions."
                      />
                    </td>
                  </tr>
                ) : (
                  payments.map((p) => (
                    <tr
                      key={p.id}
                      className="hover:bg-[#171C21]/70 transition group"
                    >
                      <td className="py-3.5 px-5 font-mono text-xs font-semibold text-[#F3F5F7]">
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/payments/${p.id}`}
                            className="hover:text-[#C6F36A] transition"
                          >
                            {p.payment_reference}
                          </Link>
                          <button
                            type="button"
                            onClick={() =>
                              handleCopyRef(p.payment_reference, p.id)
                            }
                            aria-label={`Copy ${p.payment_reference}`}
                            className="p-1 rounded text-[#6E7A87] hover:text-[#F3F5F7] hover:bg-[#1F262E] transition"
                          >
                            {copiedId === p.id ? (
                              <Check className="w-3 h-3 text-[#2DD4BF]" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 font-mono text-xs text-[#9BA5B0] tabular-nums">
                        {p.customer_id}
                      </td>
                      <td className="py-3.5 px-4 font-mono font-semibold text-xs text-[#F3F5F7] tabular-nums">
                        {p.currency} {Number(p.amount).toFixed(2)}
                      </td>
                      <td className="py-3.5 px-4 text-xs capitalize text-[#9BA5B0]">
                        {p.payment_method.replace("_", " ")}
                      </td>
                      <td className="py-3.5 px-4 text-xs font-medium text-[#F3F5F7] capitalize">
                        {p.gateway_name}
                      </td>
                      <td className="py-3.5 px-4">
                        <StatusBadge status={p.status} type="payment" />
                      </td>
                      <td className="py-3.5 px-4 text-xs font-mono text-[#6E7A87] tabular-nums">
                        {new Date(p.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="py-3.5 px-5 text-right">
                        <div className="inline-flex items-center gap-3">
                          <Link
                            href={`/investigations/new?ref=${encodeURIComponent(p.payment_reference)}`}
                            className="text-[11px] font-mono text-[#9BA5B0] hover:text-[#C6F36A] hidden sm:inline-flex items-center gap-1 transition"
                            title="Investigate this payment"
                          >
                            <ShieldAlert className="w-3 h-3" />
                            <span>Triage</span>
                          </Link>
                          <Link
                            href={`/payments/${p.id}`}
                            className="inline-flex items-center text-xs font-mono font-medium text-[#C6F36A] hover:underline"
                          >
                            <Eye className="w-3.5 h-3.5 mr-1" />
                            Inspect
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Bar */}
          <div className="px-5 py-3.5 border-t border-[#1F262E] bg-[#0B0D0F]/50 flex items-center justify-between">
            <span className="text-xs text-[#9BA5B0] tabular-nums">
              Showing{" "}
              <span className="font-mono font-semibold text-[#F3F5F7]">
                {payments.length}
              </span>{" "}
              of{" "}
              <span className="font-mono font-semibold text-[#F3F5F7]">
                {total}
              </span>{" "}
              transactions
            </span>
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || loading}
                className="inline-flex items-center px-3 py-1.5 border border-[#262F38] rounded-lg text-xs font-medium text-[#9BA5B0] bg-[#111519] hover:text-[#F3F5F7] disabled:opacity-40 transition"
              >
                <ChevronLeft className="w-3.5 h-3.5 mr-1" />
                Previous
              </button>
              <span className="text-xs text-[#9BA5B0] px-2 font-mono tabular-nums">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages || loading}
                className="inline-flex items-center px-3 py-1.5 border border-[#262F38] rounded-lg text-xs font-medium text-[#9BA5B0] bg-[#111519] hover:text-[#F3F5F7] disabled:opacity-40 transition"
              >
                Next
                <ChevronRight className="w-3.5 h-3.5 ml-1" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
