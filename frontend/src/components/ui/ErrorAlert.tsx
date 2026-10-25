import React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

interface ErrorAlertProps {
  message: string;
  code?: string;
  retryAfter?: number | null;
  onRetry?: () => void;
  className?: string;
}

export function ErrorAlert({
  message,
  code,
  retryAfter,
  onRetry,
  className = "",
}: ErrorAlertProps) {
  return (
    <div
      className={`rounded-xl border border-[#F87171]/35 bg-[#F87171]/10 p-4 text-[#F3F5F7] ${className}`}
      role="alert"
    >
      <div className="flex items-start">
        <AlertCircle className="w-5 h-5 text-[#F87171] mt-0.5 mr-3 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-xs font-mono font-semibold text-[#F87171] uppercase tracking-wider">
              {code ? `Error: ${code}` : "Request Failed"}
            </h4>
            {retryAfter && (
              <span className="text-[11px] bg-[#171C21] text-[#F87171] border border-[#F87171]/30 px-2 py-0.5 rounded font-mono tabular-nums">
                Retry in {retryAfter}s
              </span>
            )}
          </div>
          <p className="text-xs text-[#F3F5F7]/90 mt-1.5 leading-relaxed">
            {message}
          </p>

          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 inline-flex items-center px-3 py-1.5 text-xs font-medium text-[#F3F5F7] bg-[#171C21] border border-[#262F38] rounded-lg hover:bg-[#1D242B] hover:border-[#333F4C] transition"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1.5 text-[#F87171]" />
              Retry Request
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
