"use client";

import React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { AnimatedCounter } from "@/components/motion/MotionSystem";

interface MetricCardProps {
  title: string;
  value: number | string;
  description?: string;
  icon?: React.ReactNode;
  badge?: string;
  badgeColor?: "green" | "amber" | "rose" | "blue" | "slate" | "lime";
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
    green: "bg-[#2DD4BF]/10 text-[#2DD4BF] border-[#2DD4BF]/25",
    amber: "bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/25",
    rose: "bg-[#F87171]/10 text-[#F87171] border-[#F87171]/25",
    blue: "bg-[#60A5FA]/10 text-[#60A5FA] border-[#60A5FA]/25",
    lime: "bg-[#C6F36A]/10 text-[#C6F36A] border-[#C6F36A]/30",
    slate: "bg-[#171C21] text-[#9BA5B0] border-[#262F38]",
  }[badgeColor];

  const isNumericValue = typeof value === "number";

  const content = (
    <div className="rounded-xl border border-[#1F262E] bg-[#111519] p-5 hover:border-[#333F4C] hover:bg-[#14191F] transition-colors duration-200 flex flex-col justify-between h-full">
      <div>
        <div className="flex items-center justify-between mb-3.5">
          <span className="text-xs font-medium text-[#9BA5B0] tracking-tight">
            {title}
          </span>
          {icon && (
            <div className="p-2 rounded-lg bg-[#171C21] border border-[#262F38] text-[#9BA5B0]">
              {icon}
            </div>
          )}
        </div>

        <div className="flex items-baseline gap-2.5">
          {loading ? (
            <div
              className="h-8 w-20 bg-[#171C21] animate-pulse rounded-md"
              aria-label="Loading metric value"
            />
          ) : (
            <span className="text-2xl font-bold tracking-tight text-[#F3F5F7] tabular-nums font-mono">
              {isNumericValue ? <AnimatedCounter value={value} /> : value}
            </span>
          )}
          {badge && (
            <span
              className={`text-[11px] font-mono px-2 py-0.5 rounded-md font-medium border ${badgeClasses}`}
            >
              {badge}
            </span>
          )}
        </div>

        {description && (
          <p className="text-xs text-[#6E7A87] mt-2 leading-relaxed">
            {description}
          </p>
        )}
      </div>

      {href && (
        <div className="mt-4 pt-3 border-t border-[#1F262E] flex items-center justify-between text-xs font-medium text-[#9BA5B0] group-hover:text-[#C6F36A] transition-colors">
          <span>Inspect records</span>
          <ArrowUpRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
        </div>
      )}
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="block group h-full rounded-xl">
        {content}
      </Link>
    );
  }

  return content;
}
