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
  FileText,
  RefreshCw,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api, ApiError } from "@/lib/api";
import { InvestigationCase, InvestigationMetrics } from "@/lib/types";
import { MetricCard } from "@/components/ui/MetricCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ErrorAlert } from "@/components/ui/ErrorAlert";
import { EmptyState } from "@/components/ui/EmptyState";
import { TableRowSkeleton } from "@/components/ui/LoadingSkeleton";
import { LandingPage } from "@/components/landing/LandingPage";
import { RevealSection } from "@/components/motion/MotionSystem";

export default function DashboardPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [metrics, setMetrics] = useState<InvestigationMetrics | null>(null);
  const [recentCases, setRecentCases] = useState<InvestigationCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{
    message: string;
    code?: string;
    retryAfter?: number | null;
  } | null>(null);

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
    if (!authLoading && isAuthenticated) {
      loadDashboardData();
    }
  }, [authLoading, isAuthenticated, loadDashboardData]);

  // Unauthenticated visitors at `/` see the full Premium Fintech Landing Page
  if (!authLoading && !isAuthenticated) {
    return <LandingPage />;
  }

  const categoryEntries = metrics ? Object.entries(metrics.by_category) : [];
  const maxCategoryCount =
    categoryEntries.length > 0
      ? Math.max(...categoryEntries.map(([, count]) => count), 1)
      : 1;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#F3F5F7]">
            Operations Overview
          </h1>
          <p className="text-xs sm:text-sm text-[#9BA5B0] mt-1">
            Monitor real-time payment investigations, deterministic triage classifications, and grounded RAG outcomes.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={loadDashboardData}
            disabled={loading}
            className="inline-flex items-center px-3 py-2 border border-[#262F38] rounded-xl text-xs font-medium text-[#9BA5B0] hover:text-[#F3F5F7] bg-[#111519] hover:bg-[#171C21] transition disabled:opacity-50"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
          <Link
            href="/investigations"
            className="inline-flex items-center px-3.5 py-2 border border-[#262F38] rounded-xl text-xs font-medium text-[#F3F5F7] bg-[#111519] hover:bg-[#171C21] transition"
          >
            All Cases
          </Link>
          <Link
            href="/investigations/new"
            className="inline-flex items-center px-4 py-2 rounded-xl text-xs font-semibold text-[#0B0D0F] bg-[#C6F36A] hover:bg-[#D4F788] transition active:scale-[0.98]"
          >
            <Plus className="w-3.5 h-3.5 mr-1.5" />
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
      <RevealSection className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Investigations"
          value={metrics ? metrics.total_cases : 0}
          description="Recorded in authorized scope"
          icon={<FileText className="w-4 h-4 text-[#C6F36A]" />}
          loading={loading}
          href="/investigations"
        />
        <MetricCard
          title="Open Cases"
          value={metrics ? metrics.open_cases + metrics.in_progress_cases : 0}
          description="Awaiting processing or review"
          badge="Active"
          badgeColor="amber"
          icon={<Clock className="w-4 h-4 text-[#F59E0B]" />}
          loading={loading}
          href="/investigations?status=open"
        />
        <MetricCard
          title="Triaged & Grounded"
          value={metrics ? metrics.triaged_cases : 0}
          description="Autonomous RAG resolutions"
          badge="Completed"
          badgeColor="green"
          icon={<CheckCircle2 className="w-4 h-4 text-[#2DD4BF]" />}
          loading={loading}
          href="/investigations?status=triaged"
        />
        <MetricCard
          title="Escalated to Ops"
          value={metrics ? metrics.escalated_cases : 0}
          description="Requires human analyst sign-off"
          badge="High Priority"
          badgeColor="rose"
          icon={<AlertTriangle className="w-4 h-4 text-[#F87171]" />}
          loading={loading}
          href="/investigations?status=escalated"
        />
      </RevealSection>

      {/* Main Grid: Recent Investigations & Telemetry Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Investigations Table (2 Cols) */}
        <div className="lg:col-span-2 bg-[#111519] rounded-xl border border-[#1F262E] overflow-hidden flex flex-col">
          <div className="px-6 py-4 border-b border-[#1F262E] flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-[#F3F5F7]">
                Recent Investigations
              </h2>
              <p className="text-xs text-[#6E7A87] mt-0.5">
                Live transaction cases from PostgreSQL database
              </p>
            </div>
            <Link
              href="/investigations"
              className="text-xs font-medium text-[#C6F36A] hover:underline flex items-center"
            >
              <span>View all</span>
              <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Link>
          </div>

          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#0B0D0F]/60 border-b border-[#1F262E] text-[11px] font-mono font-semibold text-[#6E7A87] uppercase tracking-wider">
                  <th className="py-3 px-4">Case #</th>
                  <th className="py-3 px-4">Payment Ref</th>
                  <th className="py-3 px-4">Triage Category</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Created</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1F262E] text-xs">
                {loading ? (
                  <>
                    <TableRowSkeleton columns={6} />
                    <TableRowSkeleton columns={6} />
                    <TableRowSkeleton columns={6} />
                    <TableRowSkeleton columns={6} />
                  </>
                ) : recentCases.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-6">
                      <EmptyState
                        title="No investigations recorded yet"
                        description="Start your first payment investigation to review deterministic triage and grounded RAG citations."
                        actionText="Start Investigation"
                        actionHref="/investigations/new"
                      />
                    </td>
                  </tr>
                ) : (
                  recentCases.map((c) => (
                    <tr
                      key={c.id}
                      className="hover:bg-[#171C21]/70 transition-colors"
                    >
                      <td className="py-3.5 px-4 font-mono text-xs font-semibold text-[#F3F5F7] tabular-nums">
                        {c.case_number}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-xs text-[#9BA5B0] tabular-nums">
                        {c.payment?.payment_reference || "—"}
                      </td>
                      <td className="py-3.5 px-4 text-xs font-medium text-[#F3F5F7]">
                        {c.result?.issue_category ? (
                          <span className="capitalize">
                            {c.result.issue_category.replace(/_/g, " ")}
                          </span>
                        ) : (
                          <span className="text-[#6E7A87]">Pending</span>
                        )}
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
                          className="text-xs font-semibold text-[#C6F36A] hover:underline"
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

        {/* Right Column: Operational Shortcuts & Real Category Telemetry */}
        <div className="space-y-6">
          {/* Quick Actions Card */}
          <div className="bg-[#111519] rounded-xl border border-[#1F262E] p-5">
            <h2 className="text-sm font-semibold text-[#F3F5F7] mb-3.5">
              Operational Shortcuts
            </h2>
            <div className="space-y-2.5">
              <Link
                href="/investigations/new"
                className="flex items-center justify-between p-3 rounded-xl border border-[#1F262E] bg-[#171C21]/50 hover:border-[#333F4C] hover:bg-[#171C21] transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-[#C6F36A]/10 border border-[#C6F36A]/25 text-[#C6F36A]">
                    <ShieldAlert className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-[#F3F5F7]">
                      Run New Triage
                    </h3>
                    <p className="text-[11px] text-[#6E7A87]">
                      Analyze failure code & policy
                    </p>
                  </div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-[#6E7A87] group-hover:text-[#C6F36A] transition" />
              </Link>

              <Link
                href="/payments"
                className="flex items-center justify-between p-3 rounded-xl border border-[#1F262E] bg-[#171C21]/50 hover:border-[#333F4C] hover:bg-[#171C21] transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-[#2DD4BF]/10 border border-[#2DD4BF]/25 text-[#2DD4BF]">
                    <Search className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-[#F3F5F7]">
                      Search Payments
                    </h3>
                    <p className="text-[11px] text-[#6E7A87]">
                      Find by reference or customer
                    </p>
                  </div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-[#6E7A87] group-hover:text-[#2DD4BF] transition" />
              </Link>

              <Link
                href="/knowledge"
                className="flex items-center justify-between p-3 rounded-xl border border-[#1F262E] bg-[#171C21]/50 hover:border-[#333F4C] hover:bg-[#171C21] transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-[#60A5FA]/10 border border-[#60A5FA]/25 text-[#60A5FA]">
                    <BookOpen className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-[#F3F5F7]">
                      Policy RAG Explorer
                    </h3>
                    <p className="text-[11px] text-[#6E7A87]">
                      Hybrid search & grounded Q&A
                    </p>
                  </div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-[#6E7A87] group-hover:text-[#60A5FA] transition" />
              </Link>
            </div>
          </div>

          {/* Issue Categories Breakdown (Real Backend Data Visualization) */}
          <div className="bg-[#111519] rounded-xl border border-[#1F262E] p-5">
            <div className="flex items-center justify-between mb-1">
              <h2 className="text-sm font-semibold text-[#F3F5F7]">
                Classified Categories
              </h2>
              <span className="text-[11px] font-mono text-[#6E7A87] tabular-nums">
                {metrics ? `${metrics.total_cases} total` : ""}
              </span>
            </div>
            <p className="text-xs text-[#6E7A87] mb-4">
              Deterministic classifications from completed triage runs
            </p>

            {loading ? (
              <div className="space-y-3">
                <div className="h-6 bg-[#171C21] animate-pulse rounded-md" />
                <div className="h-6 bg-[#171C21] animate-pulse rounded-md" />
                <div className="h-6 bg-[#171C21] animate-pulse rounded-md" />
              </div>
            ) : categoryEntries.length > 0 ? (
              <div className="space-y-3.5">
                {categoryEntries.map(([category, count]) => {
                  const pct = Math.round((count / maxCategoryCount) * 100);
                  return (
                    <div key={category} className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="capitalize font-medium text-[#F3F5F7]">
                          {category.replace(/_/g, " ")}
                        </span>
                        <span className="font-mono tabular-nums bg-[#171C21] border border-[#262F38] px-2 py-0.5 rounded text-[#C6F36A]">
                          {count}
                        </span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-[#171C21] overflow-hidden">
                        <div
                          className="h-full rounded-full bg-[#C6F36A] transition-all duration-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="py-6 text-center rounded-lg border border-dashed border-[#262F38] bg-[#0B0D0F]/50">
                <p className="text-xs text-[#6E7A87]">
                  No triage categories recorded in current scope yet.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
