"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  ShieldAlert,
  Plus,
  ArrowRight,
  Search,
  BookOpen,
  CheckCircle2,
  AlertTriangle,
  Clock,
  AlertCircle,
  FileText,
  ExternalLink,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { InvestigationCase, InvestigationMetrics } from "@/lib/types";
import { MetricCard } from "@/components/ui/MetricCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ErrorAlert } from "@/components/ui/ErrorAlert";
import { EmptyState } from "@/components/ui/EmptyState";
import { TableRowSkeleton } from "@/components/ui/LoadingSkeleton";

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<InvestigationMetrics | null>(null);
  const [recentCases, setRecentCases] = useState<InvestigationCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code?: string; retryAfter?: number | null } | null>(null);

  const loadDashboardData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [metricsData, casesData] = await Promise.all([
        api.getMetrics(),
        api.listInvestigations({ page: 1, page_size: 6 }),
      ]);
      setMetrics(metricsData);
      setRecentCases(casesData.items || []);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError({
          message: err.message,
          code: err.code,
          retryAfter: err.retryAfter,
        });
      } else {
        setError({
          message: "Unable to load dashboard data from backend server.",
        });
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Operations Overview</h1>
          <p className="text-sm text-slate-500 mt-1">
            Monitor real-time payment investigations, automated triage results, and dispute telemetry.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <Link
            href="/investigations"
            className="inline-flex items-center px-3.5 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 transition shadow-2xs"
          >
            All Cases
          </Link>
          <Link
            href="/investigations/new"
            className="inline-flex items-center px-4 py-2 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 transition shadow-xs"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            New Investigation
          </Link>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <ErrorAlert
          message={error.message}
          code={error.code}
          retryAfter={error.retryAfter}
          onRetry={loadDashboardData}
        />
      )}

      {/* Genuine Backend Statistics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Investigations"
          value={metrics ? metrics.total_cases : 0}
          description="Recorded in authorized scope"
          icon={<FileText className="w-5 h-5 text-blue-600" />}
          loading={loading}
          href="/investigations"
        />
        <MetricCard
          title="Open Cases"
          value={metrics ? metrics.open_cases + metrics.in_progress_cases : 0}
          description="Awaiting processing or review"
          badge="Active"
          badgeColor="amber"
          icon={<Clock className="w-5 h-5 text-amber-600" />}
          loading={loading}
          href="/investigations?status=open"
        />
        <MetricCard
          title="Triaged & Grounded"
          value={metrics ? metrics.triaged_cases : 0}
          description="Autonomous RAG resolutions"
          badge="Completed"
          badgeColor="green"
          icon={<CheckCircle2 className="w-5 h-5 text-emerald-600" />}
          loading={loading}
          href="/investigations?status=triaged"
        />
        <MetricCard
          title="Escalated to Ops"
          value={metrics ? metrics.escalated_cases : 0}
          description="Requires human analyst sign-off"
          badge="High Priority"
          badgeColor="rose"
          icon={<AlertTriangle className="w-5 h-5 text-rose-600" />}
          loading={loading}
          href="/investigations?status=escalated"
        />
      </div>

      {/* Main Grid: Recent Investigations & Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Investigations Table (2 Cols) */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Recent Investigations</h2>
              <p className="text-xs text-slate-500 mt-0.5">Live transaction cases from backend database</p>
            </div>
            <Link
              href="/investigations"
              className="text-xs font-medium text-blue-600 hover:text-blue-700 flex items-center"
            >
              <span>View all</span>
              <ArrowRight className="w-3 h-3 ml-1" />
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/70 border-b border-slate-100 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Case #</th>
                  <th className="py-3 px-4">Payment Ref</th>
                  <th className="py-3 px-4">Triage Category</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Created</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {loading ? (
                  <>
                    <TableRowSkeleton columns={6} />
                    <TableRowSkeleton columns={6} />
                    <TableRowSkeleton columns={6} />
                    <TableRowSkeleton columns={6} />
                  </>
                ) : recentCases.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8">
                      <EmptyState
                        title="No investigations yet"
                        description="Start your first payment investigation to review automated evidence and RAG recommendations."
                        actionText="Start Investigation"
                        actionHref="/investigations/new"
                      />
                    </td>
                  </tr>
                ) : (
                  recentCases.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50/60 transition">
                      <td className="py-3 px-4 font-mono text-xs font-semibold text-slate-900">
                        {c.case_number}
                      </td>
                      <td className="py-3 px-4 font-mono text-xs text-slate-600">
                        {c.payment?.payment_reference || "—"}
                      </td>
                      <td className="py-3 px-4 text-xs font-medium text-slate-700">
                        {c.result?.issue_category ? (
                          <span className="capitalize">{c.result.issue_category.replace("_", " ")}</span>
                        ) : (
                          <span className="text-slate-400">Pending</span>
                        )}
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
                          className="text-xs font-medium text-blue-600 hover:text-blue-800"
                        >
                          Inspect &rarr;
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Quick Actions & Common Categories (1 Col) */}
        <div className="space-y-6">
          {/* Quick Actions Card */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs">
            <h2 className="text-sm font-semibold text-slate-900 mb-3">Operational Shortcuts</h2>
            <div className="space-y-2">
              <Link
                href="/investigations/new"
                className="flex items-center justify-between p-3 rounded-lg border border-slate-100 hover:border-slate-200 hover:bg-slate-50 transition group"
              >
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-blue-50 text-blue-600">
                    <ShieldAlert className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-slate-900">Run New Triage</h3>
                    <p className="text-[11px] text-slate-500">Analyze failure code & policy</p>
                  </div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-600 transition" />
              </Link>

              <Link
                href="/payments"
                className="flex items-center justify-between p-3 rounded-lg border border-slate-100 hover:border-slate-200 hover:bg-slate-50 transition group"
              >
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
                    <Search className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-slate-900">Search Payments</h3>
                    <p className="text-[11px] text-slate-500">Find by reference or customer</p>
                  </div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-emerald-600 transition" />
              </Link>

              <Link
                href="/knowledge"
                className="flex items-center justify-between p-3 rounded-lg border border-slate-100 hover:border-slate-200 hover:bg-slate-50 transition group"
              >
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-purple-50 text-purple-600">
                    <BookOpen className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-slate-900">Policy RAG Explorer</h3>
                    <p className="text-[11px] text-slate-500">Hybrid search scheme rules</p>
                  </div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-purple-600 transition" />
              </Link>
            </div>
          </div>

          {/* Issue Categories Breakdown */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs">
            <h2 className="text-sm font-semibold text-slate-900 mb-2">Classified Categories</h2>
            <p className="text-xs text-slate-500 mb-4">Grounded classifications from triage results</p>

            {loading ? (
              <div className="space-y-2">
                <div className="h-6 bg-slate-100 animate-pulse rounded" />
                <div className="h-6 bg-slate-100 animate-pulse rounded" />
              </div>
            ) : metrics && Object.keys(metrics.by_category).length > 0 ? (
              <div className="space-y-3">
                {Object.entries(metrics.by_category).map(([category, count]) => (
                  <div key={category} className="flex items-center justify-between text-xs">
                    <span className="capitalize font-medium text-slate-700">
                      {category.replace("_", " ")}
                    </span>
                    <span className="font-mono bg-slate-100 px-2 py-0.5 rounded text-slate-600">
                      {count}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">No triage categories recorded yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
