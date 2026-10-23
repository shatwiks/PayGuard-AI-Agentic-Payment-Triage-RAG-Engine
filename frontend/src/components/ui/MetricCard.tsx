import React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: number | string;
  description?: string;
  icon?: React.ReactNode;
  badge?: string;
  badgeColor?: "green" | "amber" | "rose" | "blue" | "slate";
  href?: string;
  loading?: boolean;
}

export function MetricCard({
  title,
  value,
  description,
  icon,
  badge,
  badgeColor = "slate",
  href,
  loading = false,
}: MetricCardProps) {
  const badgeClasses = {
    green: "bg-emerald-50 text-emerald-700 border-emerald-200",
    amber: "bg-amber-50 text-amber-700 border-amber-200",
    rose: "bg-rose-50 text-rose-700 border-rose-200",
    blue: "bg-blue-50 text-blue-700 border-blue-200",
    slate: "bg-slate-100 text-slate-700 border-slate-200",
  }[badgeColor];

  const content = (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:border-slate-300 transition-all">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-slate-500">{title}</span>
        {icon && <div className="text-slate-400 p-2 bg-slate-50 rounded-lg">{icon}</div>}
      </div>

      <div className="flex items-baseline space-x-2">
        {loading ? (
          <div className="h-8 w-20 bg-slate-200 animate-pulse rounded" />
        ) : (
          <span className="text-2xl font-bold tracking-tight text-slate-900">{value}</span>
        )}
        {badge && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${badgeClasses}`}>
            {badge}
          </span>
        )}
      </div>

      {description && <p className="text-xs text-slate-500 mt-2">{description}</p>}

      {href && (
        <div className="mt-3 pt-3 border-t border-slate-100 flex items-center text-xs font-medium text-blue-600 hover:text-blue-700">
          <span>View records</span>
          <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
        </div>
      )}
    </div>
  );

  if (href) {
    return <Link href={href} className="block group">{content}</Link>;
  }

  return content;
}
