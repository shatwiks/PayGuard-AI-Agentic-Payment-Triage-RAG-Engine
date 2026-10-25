import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { ToastProvider } from "@/components/ui/ToastContext";
import { AppLayout } from "@/components/layout/AppLayout";

export const metadata: Metadata = {
  title: "PayGuard AI — Agentic Payment Triage & Evidence-Grounded RAG",
  description:
    "Investigate payment failures, trace processor webhook events, and retrieve verifiable policy citations with deterministic triage and hybrid pgvector RAG.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full antialiased dark">
      <body className="min-h-[100dvh] flex flex-col bg-[#0B0D0F] text-[#F3F5F7]">
        <Suspense
          fallback={
            <div className="min-h-[100dvh] bg-[#0B0D0F] flex items-center justify-center text-xs font-mono text-[#9BA5B0]">
              Initializing PayGuard AI Workspace...
            </div>
          }
        >
          <ToastProvider>
            <AuthProvider>
              <AppLayout>{children}</AppLayout>
            </AuthProvider>
          </ToastProvider>
        </Suspense>
      </body>
    </html>
  );
}
