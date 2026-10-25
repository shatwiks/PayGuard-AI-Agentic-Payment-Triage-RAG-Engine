import React from "react";
import Link from "next/link";
import { Inbox, Plus } from "lucide-react";

interface EmptyStateProps {
  title: string;
  description: string;
  actionText?: string;
  actionHref?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
}

export function EmptyState({
  title,
  description,
  actionText,
  actionHref,
  onAction,
  icon = <Inbox className="w-8 h-8 text-[#6E7A87]" />,
}: EmptyStateProps) {
  return (
    <div className="text-center py-12 px-6 rounded-xl border border-dashed border-[#262F38] bg-[#0B0D0F]/60">
      <div className="mx-auto w-14 h-14 rounded-2xl bg-[#171C21] border border-[#262F38] flex items-center justify-center mb-4">
        {icon}
      </div>
      <h3 className="text-sm font-semibold text-[#F3F5F7] mb-1.5">{title}</h3>
      <p className="text-xs text-[#9BA5B0] max-w-md mx-auto mb-6 leading-relaxed">
        {description}
      </p>

      {actionText && actionHref && (
        <Link
          href={actionHref}
          className="inline-flex items-center px-4 py-2 text-xs font-semibold text-[#0B0D0F] bg-[#C6F36A] rounded-lg hover:bg-[#D4F788] transition active:scale-[0.98]"
        >
          <Plus className="w-3.5 h-3.5 mr-1.5" />
          {actionText}
        </Link>
      )}

      {actionText && !actionHref && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="inline-flex items-center px-4 py-2 text-xs font-semibold text-[#0B0D0F] bg-[#C6F36A] rounded-lg hover:bg-[#D4F788] transition active:scale-[0.98]"
        >
          {actionText}
        </button>
      )}
    </div>
  );
}
