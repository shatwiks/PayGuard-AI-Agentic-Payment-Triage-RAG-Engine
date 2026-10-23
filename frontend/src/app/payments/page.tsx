"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Search, Filter, RefreshCw, ChevronLeft, ChevronRight, Eye } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { PaymentSummary } from "@/lib/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ErrorAlert } from "@/components/ui/ErrorAlert";
import { EmptyState } from "@/components/ui/EmptyState";
import { TableRowSkeleton } from "@/components/ui/LoadingSkeleton";

export default function PaymentsPage() {
  const [payments, setPayments] = useState<PaymentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code?: string; retryAfter?: number | null } | null>(null);

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
    } catch (err: any) {
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
  }, [referenceQuery, statusFilter, methodFilter, gatewayFilter, page, pageSize]);

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Payment Transactions</h1>
          <p className="text-sm text-slate-500 mt-1">
            Search, filter, and inspect transaction telemetry across payment gateways.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => fetchPayments()}
            className="inline-flex items-center px-3 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 transition shadow-2xs"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
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
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-2xs">
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="lg:col-span-2 relative">
            <input
              type="text"
              placeholder="Search by payment reference (e.g. tx_...)"
              value={referenceQuery}
              onChange={(e) => setReferenceQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          </div>

          <div>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-700"
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
              value={methodFilter}
              onChange={(e) => {
                setMethodFilter(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-700"
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
              className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm rounded-lg transition shadow-xs"
            >
              Filter
            </button>
            {(referenceQuery || statusFilter || methodFilter || gatewayFilter) && (
              <button
                type="button"
                onClick={handleResetFilters}
                className="px-3 py-2 border border-slate-300 hover:bg-slate-50 text-slate-600 rounded-lg text-sm font-medium transition"
              >
                Reset
              </button>
            )}
          </div>
        </form>
      </div>

      {/* Payments Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/70 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                <th className="py-3.5 px-4">Payment Reference</th>
                <th className="py-3.5 px-4">Customer ID</th>
                <th className="py-3.5 px-4">Amount</th>
                <th className="py-3.5 px-4">Payment Rail</th>
                <th className="py-3.5 px-4">Gateway</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Created Time</th>
                <th className="py-3.5 px-4 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
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
                  <td colSpan={8} className="py-12">
                    <EmptyState
                      title="No payment records found"
                      description="Try adjusting your search criteria or filter options to locate transactions."
                    />
                  </td>
                </tr>
              ) : (
                payments.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/60 transition">
                    <td className="py-3 px-4 font-mono text-xs font-semibold text-slate-900">
                      {p.payment_reference}
                    </td>
                    <td className="py-3 px-4 font-mono text-xs text-slate-600">
                      {p.customer_id}
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-900">
                      {p.currency} {Number(p.amount).toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-xs capitalize text-slate-600">
                      {p.payment_method.replace("_", " ")}
                    </td>
                    <td className="py-3 px-4 text-xs font-medium text-slate-700 capitalize">
                      {p.gateway_name}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={p.status} type="payment" />
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500">
                      {new Date(p.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        href={`/payments/${p.id}`}
                        className="inline-flex items-center text-xs font-medium text-blue-600 hover:text-blue-800"
                      >
                        <Eye className="w-3.5 h-3.5 mr-1" />
                        Inspect
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="px-4 py-3 border-t border-slate-200 bg-slate-50/50 flex items-center justify-between">
          <span className="text-xs text-slate-500">
            Showing <span className="font-medium text-slate-800">{payments.length}</span> of{" "}
            <span className="font-medium text-slate-800">{total}</span> transactions
          </span>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="inline-flex items-center px-2.5 py-1.5 border border-slate-300 rounded-md text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 transition"
            >
              <ChevronLeft className="w-3.5 h-3.5 mr-1" />
              Previous
            </button>
            <span className="text-xs text-slate-600 px-2 font-mono">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || loading}
              className="inline-flex items-center px-2.5 py-1.5 border border-slate-300 rounded-md text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 transition"
            >
              Next
              <ChevronRight className="w-3.5 h-3.5 ml-1" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
