"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  ChevronRight,
  LogOut,
  Menu,
  Plus,
  Search,
  ShieldCheck,
} from "lucide-react";

interface HeaderProps {
  onToggleSidebar: () => void;
  title?: string;
}

export function Header({ onToggleSidebar, title }: HeaderProps) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [quickRef, setQuickRef] = useState("");

  const roleLabels: Record<string, string> = {
    admin: "Admin",
    compliance_analyst: "Compliance Analyst",
    support_agent: "Support Operator",
  };

  // Compute dynamic breadcrumb trail from current pathname
  const getBreadcrumbs = () => {
    if (pathname === "/") {
      return [{ label: "Overview", href: "/" }];
    }
    const segments = pathname.split("/").filter(Boolean);
    const crumbs: { label: string; href: string }[] = [
      { label: "Workspace", href: "/" },
    ];
    let acc = "";
    segments.forEach((seg) => {
      acc += `/${seg}`;
      const label =
        seg === "investigations"
          ? "Investigations"
          : seg === "payments"
          ? "Payments"
          : seg === "knowledge"
          ? "Knowledge Base"
          : seg === "new"
          ? "New Triage"
          : seg.length > 14
          ? `${seg.slice(0, 8)}…`
          : seg;
      crumbs.push({ label, href: acc });
    });
    return crumbs;
  };

  const breadcrumbs = getBreadcrumbs();

  const handleQuickLookup = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = quickRef.trim();
    if (!trimmed) return;
    setQuickRef("");
    router.push(`/payments/${encodeURIComponent(trimmed)}`);
  };

  return (
    <header className="h-16 bg-[#111519]/90 backdrop-blur-md border-b border-[#1F262E] px-4 sm:px-6 flex items-center justify-between gap-4 sticky top-0 z-30">
      {/* Left: Mobile Sidebar Toggle & Breadcrumbs */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="md:hidden p-2 rounded-lg text-[#9BA5B0] hover:text-[#F3F5F7] hover:bg-[#171C21]"
          aria-label="Toggle Navigation"
        >
          <Menu className="w-5 h-5" />
        </button>

        {title ? (
          <h1 className="text-base font-semibold text-[#F3F5F7] truncate">
            {title}
          </h1>
        ) : (
          <nav
            aria-label="Breadcrumb"
            className="flex items-center gap-1.5 text-xs font-medium overflow-hidden"
          >
            {breadcrumbs.map((crumb, idx) => {
              const isLast = idx === breadcrumbs.length - 1;
              return (
                <React.Fragment key={crumb.href}>
                  {idx > 0 && (
                    <ChevronRight className="w-3.5 h-3.5 text-[#6E7A87] shrink-0" />
                  )}
                  {isLast ? (
                    <span className="text-[#F3F5F7] font-semibold truncate font-mono">
                      {crumb.label}
                    </span>
                  ) : (
                    <Link
                      href={crumb.href}
                      className="text-[#9BA5B0] hover:text-[#F3F5F7] transition truncate"
                    >
                      {crumb.label}
                    </Link>
                  )}
                </React.Fragment>
              );
            })}
          </nav>
        )}
      </div>

      {/* Center/Right: Quick Reference Search + Primary Action + Operator Profile */}
      <div className="flex items-center gap-3">
        <form
          onSubmit={handleQuickLookup}
          className="hidden lg:flex items-center relative"
          role="search"
          aria-label="Quick payment reference lookup"
        >
          <Search className="w-3.5 h-3.5 text-[#6E7A87] absolute left-3 pointer-events-none" />
          <input
            type="text"
            value={quickRef}
            onChange={(e) => setQuickRef(e.target.value)}
            placeholder="Jump to payment ref (e.g. tx_...)"
            aria-label="Jump to payment reference"
            className="w-56 pl-8 pr-3 py-1.5 rounded-lg bg-[#0B0D0F] border border-[#262F38] focus:border-[#C6F36A] text-xs font-mono text-[#F3F5F7] placeholder-[#6E7A87] focus:outline-none transition"
          />
        </form>

        <Link
          href="/investigations/new"
          className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#171C21] hover:bg-[#1D242B] border border-[#262F38] text-xs font-semibold text-[#C6F36A] transition"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Investigate</span>
        </Link>

        {user ? (
          <div className="flex items-center gap-3 pl-2 border-l border-[#1F262E]">
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-xs font-semibold text-[#F3F5F7] leading-tight">
                {user.full_name || user.email}
              </span>
              <span className="text-[11px] text-[#9BA5B0] flex items-center justify-end mt-0.5">
                <ShieldCheck className="w-3 h-3 text-[#C6F36A] mr-1" />
                {roleLabels[user.role] || user.role}
              </span>
            </div>
            <div className="w-8 h-8 rounded-lg bg-[#171C21] border border-[#262F38] text-[#C6F36A] flex items-center justify-center font-mono font-semibold text-xs">
              {user.full_name
                ? user.full_name
                    .split(" ")
                    .map((n) => n[0])
                    .join("")
                    .substring(0, 2)
                    .toUpperCase()
                : user.email[0].toUpperCase()}
            </div>
            <button
              type="button"
              onClick={logout}
              title="Sign Out"
              aria-label="Sign Out"
              className="p-2 text-[#9BA5B0] hover:text-[#F87171] hover:bg-[#171C21] rounded-lg transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="h-8 w-24 bg-[#171C21] animate-pulse rounded-md" />
        )}
      </div>
    </header>
  );
}
