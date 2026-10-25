"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { ApiError } from "@/lib/api";
import {
  ArrowLeft,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  ShieldAlert,
} from "lucide-react";
import { ErrorAlert } from "@/components/ui/ErrorAlert";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<{
    message: string;
    code?: string;
    retryAfter?: number | null;
  } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setError(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError({ message: "Please enter your operator email address." });
      return;
    }
    if (!password) {
      setError({ message: "Please enter your password." });
      return;
    }

    setIsSubmitting(true);
    try {
      await login({ email: trimmedEmail, password });
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError({
          message: err.message,
          code: err.code,
          retryAfter: err.retryAfter,
        });
      } else {
        setError({
          message:
            "Unable to sign in. Please verify your credentials and try again.",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-[100dvh] flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 bg-[#0B0D0F] text-[#F3F5F7] pg-tech-grid">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex items-center justify-between mb-6">
          <Link
            href="/welcome"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-[#9BA5B0] hover:text-[#F3F5F7] transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Platform Overview</span>
          </Link>
          <span className="inline-flex items-center gap-1 text-[11px] font-mono text-[#6E7A87]">
            <Lock className="w-3 h-3 text-[#C6F36A]" />
            JWT Authenticated
          </span>
        </div>

        <div className="text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-[#111519] border border-[#C6F36A]/40 text-[#C6F36A] shadow-lg mb-4">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-[#F3F5F7]">
            Sign in to PayGuard AI
          </h2>
          <p className="mt-1.5 text-xs text-[#9BA5B0]">
            Investigate payment issues with deterministic triage and evidence-grounded RAG.
          </p>
        </div>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="pg-surface-shell">
          <div className="pg-surface-core py-8 px-6 sm:px-9">
            {error && (
              <ErrorAlert
                message={error.message}
                code={error.code}
                retryAfter={error.retryAfter}
                className="mb-6"
              />
            )}

            <form className="space-y-5" onSubmit={handleSubmit} noValidate>
              <div>
                <label
                  htmlFor="email"
                  className="block text-xs font-medium text-[#F3F5F7] mb-1.5"
                >
                  Operator Email
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="agent@payguard.ai"
                  className="w-full px-3.5 py-2.5 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-sm text-[#F3F5F7] placeholder-[#6E7A87] focus:outline-none focus:border-[#C6F36A] transition"
                />
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="block text-xs font-medium text-[#F3F5F7] mb-1.5"
                >
                  Password
                </label>
                <div className="relative">
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full px-3.5 py-2.5 pr-10 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-sm text-[#F3F5F7] placeholder-[#6E7A87] focus:outline-none focus:border-[#C6F36A] transition"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-[#6E7A87] hover:text-[#F3F5F7]"
                  >
                    {showPassword ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>

              <div className="pt-1">
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full flex justify-center items-center py-2.5 px-4 rounded-xl text-xs font-semibold text-[#0B0D0F] bg-[#C6F36A] hover:bg-[#D4F788] disabled:opacity-50 transition active:scale-[0.98]"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Authenticating...
                    </>
                  ) : (
                    "Sign In"
                  )}
                </button>
              </div>
            </form>

            <div className="mt-6 border-t border-[#1F262E] pt-4 flex items-center justify-between text-xs text-[#9BA5B0]">
              <span>New support operator?</span>
              <Link
                href="/register"
                className="font-semibold text-[#C6F36A] hover:underline"
              >
                Register an account &rarr;
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
