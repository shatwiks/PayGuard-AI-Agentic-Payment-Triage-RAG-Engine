import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { AppLayout } from "@/components/layout/AppLayout";

export const metadata: Metadata = {
  title: "PayGuard AI: Agentic Payment Triage and RAG Engine",
  description:
    "Autonomous payment investigation, deterministic triage, and policy-grounded RAG retrieval for payment operations and support engineers.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-slate-50 text-slate-900">
        <Suspense
          fallback={
            <div className="min-h-screen bg-slate-50 flex items-center justify-center text-sm text-slate-500 font-medium">
              Initializing PayGuard AI...
            </div>
          }
        >
          <AuthProvider>
            <AppLayout>{children}</AppLayout>
          </AuthProvider>
        </Suspense>
      </body>
    </html>
  );
}
