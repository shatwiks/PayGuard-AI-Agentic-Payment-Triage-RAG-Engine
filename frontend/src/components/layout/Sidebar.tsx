"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Compass,
  CreditCard,
  LayoutDashboard,
  PlusCircle,
  Search,
  ShieldAlert,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { HealthResponse } from "@/lib/types";

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  isCollapsed?: boolean;
  setIsCollapsed?: (collapsed: boolean) => void;
}

export function Sidebar({
  isOpen,
  setIsOpen,
  isCollapsed = false,
  setIsCollapsed,
}: SidebarProps) {
  const pathname = usePathname();
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    let mounted = true;
    api
      .getHealth()
      .then((h) => {
        if (mounted) setHealth(h);
      })
      .catch(() => {
        if (mounted)
          setHealth({
            status: "degraded",
            database: "disconnected",
            vector_store: "unavailable",
            version: "0.1.0",
            environment: "development",
          });
      });

    const interval = setInterval(() => {
      api
        .getHealth()
        .then((h) => mounted && setHealth(h))
        .catch(() => {});
    }, 30000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const navItems = [
    { label: "Overview", href: "/", icon: LayoutDashboard, exact: true },
    { label: "Investigations", href: "/investigations", icon: Search },
    { label: "Payments", href: "/payments", icon: CreditCard },
    { label: "Knowledge Base", href: "/knowledge", icon: BookOpen },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/70 backdrop-blur-xs md:hidden"
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        aria-label="Workspace Sidebar Navigation"
        className={`fixed top-0 bottom-0 left-0 z-50 bg-[#111519] border-r border-[#1F262E] text-[#9BA5B0] flex flex-col transition-all duration-200 md:static md:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        } ${isCollapsed ? "md:w-20" : "w-64"}`}
      >
        {/* Brand Header */}
        <div className="h-16 px-4 flex items-center justify-between border-b border-[#1F262E]">
          <Link
            href="/"
            className="flex items-center gap-2.5 min-w-0"
            title="PayGuard AI Console"
          >
            <div className="w-8 h-8 rounded-lg bg-[#171C21] border border-[#C6F36A]/45 flex items-center justify-center text-[#C6F36A] shrink-0">
              <ShieldAlert className="w-4 h-4" />
            </div>
            {!isCollapsed && (
              <div className="flex flex-col min-w-0">
                <span className="font-bold text-[#F3F5F7] tracking-tight text-sm leading-none truncate">
                  PayGuard{" "}
                  <span className="text-[#C6F36A] font-mono text-[11px]">
                    AI
                  </span>
                </span>
                <span className="text-[10px] text-[#6E7A87] font-mono uppercase tracking-wider mt-1 truncate">
                  Triage & RAG Engine
                </span>
              </div>
            )}
          </Link>

          <div className="flex items-center gap-1">
            {setIsCollapsed && (
              <button
                type="button"
                onClick={() => setIsCollapsed(!isCollapsed)}
                aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                className="hidden md:inline-flex p-1.5 rounded-lg text-[#6E7A87] hover:text-[#F3F5F7] hover:bg-[#171C21] transition"
              >
                {isCollapsed ? (
                  <ChevronRight className="w-4 h-4" />
                ) : (
                  <ChevronLeft className="w-4 h-4" />
                )}
              </button>
            )}
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              aria-label="Close mobile navigation"
              className="md:hidden p-1.5 rounded-lg text-[#9BA5B0] hover:text-[#F3F5F7]"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Primary Action Button */}
        <div className="p-3.5">
          <Link
            href="/investigations/new"
            onClick={() => setIsOpen(false)}
            title="New Investigation"
            className={`w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-[#C6F36A] hover:bg-[#D4F788] text-[#0B0D0F] font-semibold text-xs transition active:scale-[0.98] ${
              isCollapsed ? "px-2" : ""
            }`}
          >
            <PlusCircle className="w-4 h-4 shrink-0" />
            {!isCollapsed && <span>New Investigation</span>}
          </Link>
        </div>

        {/* Operational Navigation Links */}
        <nav
          aria-label="Operational navigation"
          className="flex-1 px-3 py-2 space-y-1 overflow-y-auto"
        >
          {navItems.map((item) => {
            const isActive = item.exact
              ? pathname === item.href
              : pathname.startsWith(item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setIsOpen(false)}
                title={item.label}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition ${
                  isActive
                    ? "bg-[#171C21] text-[#F3F5F7] border border-[#262F38]"
                    : "text-[#9BA5B0] hover:text-[#F3F5F7] hover:bg-[#171C21]/60 border border-transparent"
                } ${isCollapsed ? "justify-center px-2" : ""}`}
              >
                <Icon
                  className={`w-4 h-4 shrink-0 ${
                    isActive ? "text-[#C6F36A]" : "text-[#6E7A87]"
                  }`}
                />
                {!isCollapsed && <span>{item.label}</span>}
              </Link>
            );
          })}

          <div className="pt-4 mt-4 border-t border-[#1F262E]">
            <Link
              href="/welcome"
              onClick={() => setIsOpen(false)}
              title="Platform Overview & Architecture"
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium text-[#6E7A87] hover:text-[#F3F5F7] hover:bg-[#171C21]/60 transition ${
                isCollapsed ? "justify-center px-2" : ""
              }`}
            >
              <Compass className="w-4 h-4 shrink-0 text-[#6E7A87]" />
              {!isCollapsed && <span>Platform Overview</span>}
            </Link>
          </div>
        </nav>

        {/* System Health / Telemetry Footer */}
        <div className="p-3.5 border-t border-[#1F262E] bg-[#0B0D0F]/60">
          {isCollapsed ? (
            <div
              className="flex justify-center"
              title={`Engine: ${health?.status || "checking"}`}
            >
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  health?.status === "healthy" ? "bg-[#2DD4BF]" : "bg-[#F59E0B]"
                }`}
              />
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#9BA5B0] flex items-center text-[11px]">
                  <Activity className="w-3.5 h-3.5 mr-1.5 text-[#6E7A87]" />
                  API & RAG Engine
                </span>
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded-md font-mono text-[10px] border ${
                    health?.status === "healthy"
                      ? "bg-[#2DD4BF]/10 text-[#2DD4BF] border-[#2DD4BF]/25"
                      : "bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/25"
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                      health?.status === "healthy" ? "bg-[#2DD4BF]" : "bg-[#F59E0B]"
                    }`}
                  />
                  {health ? health.status.toUpperCase() : "CHECKING"}
                </span>
              </div>
              <div className="mt-2 text-[10px] font-mono text-[#6E7A87] flex justify-between">
                <span>DB: {health?.database || "connected"}</span>
                <span>Vector: {health?.vector_store || "pgvector"}</span>
              </div>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
