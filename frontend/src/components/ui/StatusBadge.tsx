import React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  RefreshCcw,
  ShieldAlert,
  XCircle,
} from "lucide-react";

interface StatusBadgeProps {
  status: string;
  type?: "payment" | "case" | "priority";
  className?: string;
}

/**
 * Semantic dark-fintech status indicator.
 * Combines text + distinct iconography so status never relies solely on color (WCAG 2.2 AA).
 */
export function StatusBadge({
  status,
  type = "case",
  className = "",
}: StatusBadgeProps) {
  const norm = status.toLowerCase();

  let bg = "bg-[#171C21]";
  let text = "text-[#9BA5B0]";
  let border = "border-[#262F38]";
  let indicator: React.ReactNode = (
    <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-current opacity-80" />
  );

  if (type === "payment") {
    switch (norm) {
      case "captured":
      case "authorized":
        bg = "bg-[#2DD4BF]/10";
        text = "text-[#2DD4BF]";
        border = "border-[#2DD4BF]/25";
        indicator = <CheckCircle2 className="w-3 h-3 mr-1 shrink-0" />;
        break;
      case "pending":
        bg = "bg-[#F59E0B]/10";
        text = "text-[#F59E0B]";
        border = "border-[#F59E0B]/25";
        indicator = <Clock className="w-3 h-3 mr-1 shrink-0" />;
        break;
      case "failed":
      case "disputed":
        bg = "bg-[#F87171]/10";
        text = "text-[#F87171]";
        border = "border-[#F87171]/30";
        indicator = <XCircle className="w-3 h-3 mr-1 shrink-0" />;
        break;
      case "reversed":
      case "refunded":
        bg = "bg-[#60A5FA]/10";
        text = "text-[#60A5FA]";
        border = "border-[#60A5FA]/25";
        indicator = <RefreshCcw className="w-3 h-3 mr-1 shrink-0" />;
        break;
    }
  } else if (type === "priority") {
    switch (norm) {
      case "urgent":
        bg = "bg-[#F87171]/12";
        text = "text-[#F87171]";
        border = "border-[#F87171]/35";
        indicator = <ShieldAlert className="w-3 h-3 mr-1 shrink-0" />;
        break;
      case "high":
        bg = "bg-[#F59E0B]/12";
        text = "text-[#F59E0B]";
        border = "border-[#F59E0B]/30";
        indicator = <AlertTriangle className="w-3 h-3 mr-1 shrink-0" />;
        break;
      case "medium":
        bg = "bg-[#60A5FA]/10";
        text = "text-[#60A5FA]";
        border = "border-[#60A5FA]/25";
        break;
      case "low":
        bg = "bg-[#171C21]";
        text = "text-[#9BA5B0]";
        border = "border-[#262F38]";
        break;
    }
  } else {
    // case status: open, in_progress, triaged, escalated, closed
    switch (norm) {
      case "triaged":
        bg = "bg-[#2DD4BF]/10";
        text = "text-[#2DD4BF]";
        border = "border-[#2DD4BF]/25";
        indicator = <CheckCircle2 className="w-3 h-3 mr-1 shrink-0" />;
        break;
      case "in_progress":
        bg = "bg-[#60A5FA]/10";
        text = "text-[#60A5FA]";
        border = "border-[#60A5FA]/25";
        indicator = <Clock className="w-3 h-3 mr-1 shrink-0" />;
        break;
      case "open":
        bg = "bg-[#F59E0B]/10";
        text = "text-[#F59E0B]";
        border = "border-[#F59E0B]/25";
        indicator = <Clock className="w-3 h-3 mr-1 shrink-0" />;
        break;
      case "escalated":
        bg = "bg-[#F87171]/10";
        text = "text-[#F87171]";
        border = "border-[#F87171]/30";
        indicator = <AlertTriangle className="w-3 h-3 mr-1 shrink-0" />;
        break;
      case "closed":
        bg = "bg-[#171C21]";
        text = "text-[#9BA5B0]";
        border = "border-[#262F38]";
        break;
    }
  }

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-[11px] font-mono font-medium border ${bg} ${text} ${border} ${className}`}
    >
      {indicator}
      {status.toUpperCase().replace(/_/g, " ")}
    </span>
  );
}
