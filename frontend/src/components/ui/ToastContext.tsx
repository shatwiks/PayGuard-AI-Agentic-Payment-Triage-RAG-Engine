"use client";

import React, { createContext, useCallback, useContext, useState } from "react";
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from "lucide-react";

export type ToastVariant = "success" | "warning" | "error" | "info";

export interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastContextType {
  notify: (toast: Omit<ToastItem, "id">) => void;
  addToast: (title: string, variant?: ToastVariant, description?: string) => void;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const notify = useCallback(
    (toast: Omit<ToastItem, "id">) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((prev) => [...prev.slice(-3), { ...toast, id }]);
      setTimeout(() => {
        dismiss(id);
      }, 4500);
    },
    [dismiss]
  );

  const addToast = useCallback(
    (title: string, variant: ToastVariant = "info", description?: string) => {
      notify({ title, variant, description });
    },
    [notify]
  );

  const variantConfig: Record<
    ToastVariant,
    { icon: React.ReactNode; border: string; badge: string }
  > = {
    success: {
      icon: <CheckCircle2 className="w-4 h-4 text-[#2DD4BF] shrink-0" />,
      border: "border-[#2DD4BF]/35 bg-[#111519]",
      badge: "text-[#2DD4BF]",
    },
    warning: {
      icon: <AlertTriangle className="w-4 h-4 text-[#F59E0B] shrink-0" />,
      border: "border-[#F59E0B]/35 bg-[#111519]",
      badge: "text-[#F59E0B]",
    },
    error: {
      icon: <AlertCircle className="w-4 h-4 text-[#F87171] shrink-0" />,
      border: "border-[#F87171]/35 bg-[#111519]",
      badge: "text-[#F87171]",
    },
    info: {
      icon: <Info className="w-4 h-4 text-[#60A5FA] shrink-0" />,
      border: "border-[#60A5FA]/35 bg-[#111519]",
      badge: "text-[#60A5FA]",
    },
  };

  return (
    <ToastContext.Provider value={{ notify, addToast, dismiss }}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="fixed bottom-4 right-4 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none px-4 sm:px-0"
      >
        {toasts.map((t) => {
          const cfg = variantConfig[t.variant];
          return (
            <div
              key={t.id}
              role="status"
              className={`pointer-events-auto rounded-xl border ${cfg.border} p-3.5 shadow-[0_16px_40px_-12px_rgba(0,0,0,0.85)] flex items-start gap-3 transition-all duration-200`}
            >
              <div className="mt-0.5">{cfg.icon}</div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-[#F3F5F7] leading-snug">
                  {t.title}
                </p>
                {t.description && (
                  <p className="text-[11px] text-[#9BA5B0] mt-0.5 leading-relaxed break-words">
                    {t.description}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss notification"
                className="text-[#6E7A87] hover:text-[#F3F5F7] p-1 rounded-md transition"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextType {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    return {
      notify: () => {},
      addToast: () => {},
      dismiss: () => {},
    };
  }
  return ctx;
}
