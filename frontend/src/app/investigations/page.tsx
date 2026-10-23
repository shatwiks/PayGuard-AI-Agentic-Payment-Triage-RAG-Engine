"use client";

import React, { useEffect, useState, useCallback, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Search,
  Plus,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Eye,
  Filter,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { InvestigationCase, CaseStatus, PriorityLevel } from "@/lib/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ErrorAlert } from "@/components/ui/ErrorAlert";
import { EmptyState } from "@/components/ui/EmptyState";
import { TableRowSkeleton } from "@/components/ui/LoadingSkeleton";

function InvestigationsList() {
  const searchParams = useSearchParams();
  const initialStatus = searchParams.get("status") || "";

  const [cases, setCases] = useState<InvestigationCase[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code?: string; retryAfter?: number | null } | null>(null);

  const [statusFilter, setStatusFilter] = useState(initialStatus);
  const [priorityFilter, setPriorityFilter] = useState("");

  const fetchCases = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listInvestigations({
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        page,
        page_size: pageSize,
      });
      setCases(res.items || []);
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
          message: "Unable to load investigation records.",
        });
      }
    } finally {
      setLoading(false);
    }
  }, [statusFilter, priorityFilter, page, pageSize]);

  useEffect(() => {
    fetchCases();
  }, [fetchCases]);

  const handleResetFilters = () => {
    setStatusFilter("");
    setPriorityFilter("");
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Investigation Cases</h1>
          <p className="text-sm text-slate-500 mt-1">
            Review past triage outcomes, audit records, and grounding evidence packages.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => fetchCases()}
            className="inline-flex items-center px-3 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 transition shadow-2xs"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Refresh
          </button>
          <Link
            href="/investigations/new"
            className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm rounded-lg shadow-xs transition"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            New Investigation
          </Link>
        </div>
      </div>

      {error && (
        <ErrorAlert
          message={error.message}
          code={error.code}
          retryAfter={error.retryAfter}
          onRetry={fetchCases}
        />
      )}

      {/* Filter Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-2xs">
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <div className="w-full sm:w-48">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-700"
            >
              <option value="">All Case Statuses</option>
              <option value="open">Open</option>
              <option value="in_progress">In Progress</option>
              <option value="triaged">Triaged</option>
              <option value="escalated">Escalated</option>
              <option value="closed">Closed</option>
            </select>
          </div>

          <div className="w-full sm:w-48">
            <select
              value={priorityFilter}
              onChange={(e) => {
                setPriorityFilter(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-700"
            >
              <option value="">All Priorities</option>
              <option value="urgent">Urgent</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          {(statusFilter || priorityFilter) && (
            <button
              onClick={handleResetFilters}
              className="text-xs font-medium text-slate-500 hover:text-slate-800 px-3 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 transition"
            >
              Clear Filters
            </button>
          )}
        </div>
      </div>

      {/* Investigations Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/70 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                <th className="py-3.5 px-4">Case #</th>
                <th className="py-3.5 px-4">Payment Reference</th>
                <th className="py-3.5 px-4">Customer Inquiry</th>
                <th className="py-3.5 px-4">Category</th>
                <th className="py-3.5 px-4">Priority</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Timestamp</th>
                <th className="py-3.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {loading ? (
                <>
                  <TableRowSkeleton columns={8} />
                  <TableRowSkeleton columns={8} />
                  <TableRowSkeleton columns={8} />
                  <TableRowSkeleton columns={8} />
                </>
              ) : cases.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12">
                    <EmptyState
                      title="No investigations found"
                      description="No investigation cases match your current filters. Start a new investigation to begin."
                      actionText="Start Investigation"
                      actionHref="/investigations/new"
                    />
                  </td>
                </tr>
              ) : (
                cases.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50/60 transition">
                    <td className="py-3 px-4 font-mono text-xs font-semibold text-slate-900">
                      {c.case_number}
                    </td>
                    <td className="py-3 px-4 font-mono text-xs text-slate-600">
                      {c.payment?.payment_reference || "—"}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-700 max-w-xs truncate">
                      {c.customer_query}
                    </td>
                    <td className="py-3 px-4 text-xs font-medium text-slate-800 capitalize">
                      {c.result?.issue_category ? (
                        c.result.issue_category.replace("_", " ")
                      ) : (
                        <span className="text-slate-400">Pending</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={c.priority} type="priority" />
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={c.status} type="case" />
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500">
                      {new Date(c.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        href={`/investigations/${c.id}`}
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
            Showing <span className="font-medium text-slate-800">{cases.length}</span> of{" "}
            <span className="font-medium text-slate-800">{total}</span> cases
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

export default function InvestigationsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-slate-500">Loading investigations...</div>}>
      <InvestigationsList />
    </Suspense>
  );
}
