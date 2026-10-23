import React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

interface ErrorAlertProps {
  message: string;
  code?: string;
  retryAfter?: number | null;
  onRetry?: () => void;
  className?: string;
}

export function ErrorAlert({ message, code, retryAfter, onRetry, className = "" }: ErrorAlertProps) {
  return (
    <div
      className={`rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-900 ${className}`}
      role="alert"
    >
      <div className="flex items-start">
        <AlertCircle className="w-5 h-5 text-rose-600 mt-0.5 mr-3 shrink-0" />
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-rose-950">
              {code ? `Error: ${code}` : "Request Failed"}
            </h4>
            {retryAfter && (
              <span className="text-xs bg-rose-100 text-rose-700 px-2 py-0.5 rounded font-mono">
                Retry in {retryAfter}s
              </span>
            )}
          </div>
          <p className="text-sm text-rose-700 mt-1">{message}</p>

          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 inline-flex items-center px-3 py-1.5 text-xs font-medium text-rose-800 bg-rose-100 rounded-md hover:bg-rose-200 transition"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Try Again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
