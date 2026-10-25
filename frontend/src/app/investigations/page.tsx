"use client";

import React, { useEffect, useState, useCallback, useMemo, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  Eye,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { InvestigationCase } from "@/lib/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ErrorAlert } from "@/components/ui/ErrorAlert";
import { EmptyState } from "@/components/ui/EmptyState";
import { TableRowSkeleton } from "@/components/ui/LoadingSkeleton";
import { useToast } from "@/components/ui/ToastContext";

function InvestigationsList() {
  const searchParams = useSearchParams();
  const initialStatus = searchParams.get("status") || "";
  const { notify } = useToast();

  const [cases, setCases] = useState<InvestigationCase[]>([]);
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

  const [statusFilter, setStatusFilter] = useState(initialStatus);
  const [priorityFilter, setPriorityFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");

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
    setSearchQuery("");
    setSortOrder("desc");
    setPage(1);
  };

  const displayedCases = useMemo(() => {
    let list = [...cases];
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (c) =>
          c.case_number.toLowerCase().includes(q) ||
          (c.payment?.payment_reference || "").toLowerCase().includes(q) ||
          c.customer_query.toLowerCase().includes(q) ||
          (c.result?.issue_category || "").toLowerCase().includes(q)
      );
    }
    list.sort((a, b) => {
      const tA = new Date(a.created_at).getTime();
      const tB = new Date(b.created_at).getTime();
      return sortOrder === "desc" ? tB - tA : tA - tB;
    });
    return list;
  }, [cases, searchQuery, sortOrder]);

  const handleCopyCase = (caseNumber: string) => {
    navigator.clipboard.writeText(caseNumber);
    notify({
      title: "Case identifier copied",
      description: `${caseNumber} copied to clipboard.`,
      variant: "info",
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#F3F5F7]">
            Investigation Cases
          </h1>
          <p className="text-xs sm:text-sm text-[#9BA5B0] mt-1">
            Review past triage outcomes, audit records, and grounding evidence packages.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => fetchCases()}
            disabled={loading}
            className="inline-flex items-center px-3 py-2 border border-[#262F38] rounded-xl text-xs font-medium text-[#9BA5B0] hover:text-[#F3F5F7] bg-[#111519] hover:bg-[#171C21] transition disabled:opacity-50"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
          <Link
            href="/investigations/new"
            className="inline-flex items-center px-4 py-2 bg-[#C6F36A] hover:bg-[#D4F788] text-[#0B0D0F] font-semibold text-xs rounded-xl transition active:scale-[0.98]"
          >
            <Plus className="w-3.5 h-3.5 mr-1.5" />
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

      {/* Search, Filter & Sort Bar */}
      <div className="bg-[#111519] rounded-xl border border-[#1F262E] p-4">
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-[#6E7A87] absolute left-3.5 top-2.5 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter current page by case #, payment ref, category, or inquiry text..."
              aria-label="Filter investigation cases"
              className="w-full pl-9 pr-3 py-2 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-xs text-[#F3F5F7] placeholder-[#6E7A87] focus:outline-none focus:border-[#C6F36A] transition"
            />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              aria-label="Filter by case status"
              className="px-3 py-2 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-xs text-[#F3F5F7] focus:outline-none focus:border-[#C6F36A]"
            >
              <option value="">All Case Statuses</option>
              <option value="open">Open</option>
              <option value="in_progress">In Progress</option>
              <option value="triaged">Triaged</option>
              <option value="escalated">Escalated</option>
              <option value="closed">Closed</option>
            </select>

            <select
              value={priorityFilter}
              onChange={(e) => {
                setPriorityFilter(e.target.value);
                setPage(1);
              }}
              aria-label="Filter by priority"
              className="px-3 py-2 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-xs text-[#F3F5F7] focus:outline-none focus:border-[#C6F36A]"
            >
              <option value="">All Priorities</option>
              <option value="urgent">Urgent</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>

            <button
              type="button"
              onClick={() =>
                setSortOrder((prev) => (prev === "desc" ? "asc" : "desc"))
              }
              className="inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-[#0B0D0F] border border-[#262F38] hover:border-[#333F4C] rounded-xl text-xs font-mono text-[#9BA5B0] hover:text-[#F3F5F7] transition"
            >
              <ArrowUpDown className="w-3.5 h-3.5 text-[#C6F36A]" />
              <span>{sortOrder === "desc" ? "Newest First" : "Oldest First"}</span>
            </button>
          </div>

          {(statusFilter || priorityFilter || searchQuery) && (
            <button
              type="button"
              onClick={handleResetFilters}
              className="text-xs font-medium text-[#9BA5B0] hover:text-[#F3F5F7] px-3 py-2 border border-[#262F38] rounded-xl hover:bg-[#171C21] transition"
            >
              Clear Filters
            </button>
          )}
        </div>
      </div>

      {/* Investigations Table */}
      <div className="bg-[#111519] rounded-xl border border-[#1F262E] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#0B0D0F]/60 border-b border-[#1F262E] text-[11px] font-mono font-semibold text-[#6E7A87] uppercase tracking-wider">
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
            <tbody className="divide-y divide-[#1F262E] text-xs">
              {loading ? (
                <>
                  <TableRowSkeleton columns={8} />
                  <TableRowSkeleton columns={8} />
                  <TableRowSkeleton columns={8} />
                  <TableRowSkeleton columns={8} />
                </>
              ) : displayedCases.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8">
                    <EmptyState
                      title="No investigations found"
                      description="No investigation cases match your current filters. Start a new investigation or reset active filters."
                      actionText="Start Investigation"
                      actionHref="/investigations/new"
                    />
                  </td>
                </tr>
              ) : (
                displayedCases.map((c) => (
                  <tr
                    key={c.id}
                    className="hover:bg-[#171C21]/70 transition-colors"
                  >
                    <td className="py-3.5 px-4 font-mono text-xs font-semibold text-[#F3F5F7] tabular-nums">
                      <div className="flex items-center gap-1.5">
                        <span>{c.case_number}</span>
                        <button
                          type="button"
                          onClick={() => handleCopyCase(c.case_number)}
                          aria-label={`Copy ${c.case_number}`}
                          className="p-1 text-[#6E7A87] hover:text-[#C6F36A] rounded transition"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs text-[#9BA5B0] tabular-nums">
                      {c.payment ? (
                        <Link
                          href={`/payments/${c.payment.id}`}
                          className="hover:text-[#C6F36A] transition"
                        >
                          {c.payment.payment_reference}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-xs text-[#9BA5B0] max-w-xs truncate">
                      {c.customer_query}
                    </td>
                    <td className="py-3.5 px-4 text-xs font-medium text-[#F3F5F7] capitalize">
                      {c.result?.issue_category ? (
                        c.result.issue_category.replace(/_/g, " ")
                      ) : (
                        <span className="text-[#6E7A87]">Pending</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={c.priority} type="priority" />
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={c.status} type="case" />
                    </td>
                    <td className="py-3.5 px-4 text-xs text-[#9BA5B0] font-mono tabular-nums">
                      {new Date(c.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link
                        href={`/investigations/${c.id}`}
                        className="inline-flex items-center text-xs font-semibold text-[#C6F36A] hover:underline"
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
        <div className="px-4 py-3.5 border-t border-[#1F262E] bg-[#0B0D0F]/50 flex flex-col sm:flex-row items-center justify-between gap-3">
          <span className="text-xs text-[#9BA5B0] font-mono tabular-nums">
            Showing <span className="text-[#F3F5F7] font-semibold">{displayedCases.length}</span> of{" "}
            <span className="text-[#F3F5F7] font-semibold">{total}</span> cases
          </span>
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="inline-flex items-center px-3 py-1.5 border border-[#262F38] rounded-lg text-xs font-medium text-[#F3F5F7] bg-[#171C21] hover:bg-[#1D242B] disabled:opacity-40 transition"
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
              className="inline-flex items-center px-3 py-1.5 border border-[#262F38] rounded-lg text-xs font-medium text-[#F3F5F7] bg-[#171C21] hover:bg-[#1D242B] disabled:opacity-40 transition"
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
    <Suspense
      fallback={
        <div className="p-8 text-xs font-mono text-[#9BA5B0]">
          Loading investigation cases...
        </div>
      }
    >
      <InvestigationsList />
    </Suspense>
  );
}
