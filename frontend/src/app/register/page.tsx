"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { ApiError } from "@/lib/api";
import { ArrowLeft, Eye, EyeOff, Loader2, ShieldAlert } from "lucide-react";
import { ErrorAlert } from "@/components/ui/ErrorAlert";

export default function RegisterPage() {
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("support_agent");
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

    if (!fullName.trim()) {
      setError({ message: "Please enter your full name." });
      return;
    }
    if (!email.trim()) {
      setError({ message: "Please enter your work email address." });
      return;
    }
    if (password.length < 8) {
      setError({ message: "Password must be at least 8 characters long." });
      return;
    }

    setIsSubmitting(true);
    try {
      await register({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        role,
      });
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError({
          message: err.message,
          code: err.code,
          retryAfter: err.retryAfter,
        });
      } else {
        setError({
          message: "Unable to create operator account. Please try again.",
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
          <span className="text-[11px] font-mono text-[#6E7A87]">
            RBAC Provisioning
          </span>
        </div>

        <div className="text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-[#111519] border border-[#C6F36A]/40 text-[#C6F36A] shadow-lg mb-4">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-[#F3F5F7]">
            Register Support Personnel
          </h2>
          <p className="mt-1.5 text-xs text-[#9BA5B0]">
            Provision an operator account for payment triage and grounded policy RAG.
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

            <form className="space-y-4" onSubmit={handleSubmit} noValidate>
              <div>
                <label
                  htmlFor="fullName"
                  className="block text-xs font-medium text-[#F3F5F7] mb-1.5"
                >
                  Full Name
                </label>
                <input
                  id="fullName"
                  name="fullName"
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Alex Rivera"
                  className="w-full px-3.5 py-2.5 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-sm text-[#F3F5F7] placeholder-[#6E7A87] focus:outline-none focus:border-[#C6F36A] transition"
                />
              </div>

              <div>
                <label
                  htmlFor="email"
                  className="block text-xs font-medium text-[#F3F5F7] mb-1.5"
                >
                  Work Email
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alex.rivera@payguard.ai"
                  className="w-full px-3.5 py-2.5 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-sm text-[#F3F5F7] placeholder-[#6E7A87] focus:outline-none focus:border-[#C6F36A] transition"
                />
              </div>

              <div>
                <label
                  htmlFor="role"
                  className="block text-xs font-medium text-[#F3F5F7] mb-1.5"
                >
                  Operational Role
                </label>
                <select
                  id="role"
                  name="role"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-[#0B0D0F] border border-[#262F38] rounded-xl text-sm text-[#F3F5F7] focus:outline-none focus:border-[#C6F36A] transition"
                >
                  <option value="support_agent">
                    Support Agent (Triage & Investigate)
                  </option>
                  <option value="compliance_analyst">
                    Compliance Analyst (All Cases & Ingestion)
                  </option>
                  <option value="admin">Administrator (Full Access)</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="block text-xs font-medium text-[#F3F5F7] mb-1.5"
                >
                  Password (min. 8 characters)
                </label>
                <div className="relative">
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
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

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full flex justify-center items-center py-2.5 px-4 rounded-xl text-xs font-semibold text-[#0B0D0F] bg-[#C6F36A] hover:bg-[#D4F788] disabled:opacity-50 transition active:scale-[0.98]"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Creating Account...
                    </>
                  ) : (
                    "Register Account"
                  )}
                </button>
              </div>
            </form>

            <div className="mt-6 border-t border-[#1F262E] pt-4 flex items-center justify-between text-xs text-[#9BA5B0]">
              <span>Already have an account?</span>
              <Link
                href="/login"
                className="font-semibold text-[#C6F36A] hover:underline"
              >
                Sign in &rarr;
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
