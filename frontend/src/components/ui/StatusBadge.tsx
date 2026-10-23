import React from "react";

interface StatusBadgeProps {
  status: string;
  type?: "payment" | "case" | "priority";
  className?: string;
}

export function StatusBadge({ status, type = "case", className = "" }: StatusBadgeProps) {
  const norm = status.toLowerCase();

  let bg = "bg-slate-100";
  let text = "text-slate-700";
  let border = "border-slate-200";

  if (type === "payment") {
    switch (norm) {
      case "captured":
      case "authorized":
        bg = "bg-emerald-50";
        text = "text-emerald-700";
        border = "border-emerald-200";
        break;
      case "pending":
        bg = "bg-amber-50";
        text = "text-amber-700";
        border = "border-amber-200";
        break;
      case "failed":
      case "disputed":
        bg = "bg-rose-50";
        text = "text-rose-700";
        border = "border-rose-200";
        break;
      case "reversed":
      case "refunded":
        bg = "bg-purple-50";
        text = "text-purple-700";
        border = "border-purple-200";
        break;
    }
  } else if (type === "priority") {
    switch (norm) {
      case "urgent":
        bg = "bg-red-50";
        text = "text-red-700";
        border = "border-red-200";
        break;
      case "high":
        bg = "bg-orange-50";
        text = "text-orange-700";
        border = "border-orange-200";
        break;
      case "medium":
        bg = "bg-blue-50";
        text = "text-blue-700";
        border = "border-blue-200";
        break;
      case "low":
        bg = "bg-slate-50";
        text = "text-slate-600";
        border = "border-slate-200";
        break;
    }
  } else {
    // case status: open, in_progress, triaged, escalated, closed
    switch (norm) {
      case "triaged":
        bg = "bg-emerald-50";
        text = "text-emerald-700";
        border = "border-emerald-200";
        break;
      case "in_progress":
        bg = "bg-blue-50";
        text = "text-blue-700";
        border = "border-blue-200";
        break;
      case "open":
        bg = "bg-amber-50";
        text = "text-amber-700";
        border = "border-amber-200";
        break;
      case "escalated":
        bg = "bg-rose-50";
        text = "text-rose-700";
        border = "border-rose-200";
        break;
      case "closed":
        bg = "bg-slate-100";
        text = "text-slate-600";
        border = "border-slate-300";
        break;
    }
  }

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${bg} ${text} ${border} ${className}`}
    >
      <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-current opacity-70" />
      {status.toUpperCase().replace("_", " ")}
    </span>
  );
}
