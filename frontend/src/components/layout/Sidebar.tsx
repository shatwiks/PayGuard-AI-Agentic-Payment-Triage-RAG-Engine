"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ShieldAlert,
  LayoutDashboard,
  Search,
  CreditCard,
  BookOpen,
  Activity,
  PlusCircle,
  Menu,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { HealthResponse } from "@/lib/types";

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
}

export function Sidebar({ isOpen, setIsOpen }: SidebarProps) {
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
          className="fixed inset-0 z-40 bg-slate-900/40 md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-slate-900 text-slate-300 flex flex-col transition-transform duration-200 md:static md:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Logo and Brand */}
        <div className="h-16 px-6 flex items-center justify-between border-b border-slate-800">
          <Link href="/" className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-white tracking-tight text-base leading-none">
                PayGuard <span className="text-blue-400 font-semibold text-xs">AI</span>
              </span>
              <span className="text-[10px] text-slate-400 tracking-wider uppercase font-medium mt-1">
                Triage & RAG Console
              </span>
            </div>
          </Link>
          <button
            onClick={() => setIsOpen(false)}
            className="md:hidden text-slate-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Quick Action Button */}
        <div className="p-4">
          <Link
            href="/investigations/new"
            className="w-full flex items-center justify-center space-x-2 px-3 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm transition shadow-sm"
          >
            <PlusCircle className="w-4 h-4" />
            <span>New Investigation</span>
          </Link>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
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
                className={`flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                  isActive
                    ? "bg-slate-800 text-white border-l-2 border-blue-500"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? "text-blue-400" : "text-slate-400"}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* System Health / Telemetry Indicator */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/40">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400 flex items-center">
              <Activity className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
              API & RAG Engine
            </span>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full font-mono text-[11px] ${
                health?.status === "healthy"
                  ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800/60"
                  : "bg-amber-950/80 text-amber-400 border border-amber-800/60"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                  health?.status === "healthy" ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
                }`}
              />
              {health ? health.status.toUpperCase() : "CHECKING"}
            </span>
          </div>
          <div className="mt-2 text-[11px] text-slate-500 flex justify-between">
            <span>DB: {health?.database || "ready"}</span>
            <span>Vector: {health?.vector_store || "pgvector"}</span>
          </div>
        </div>
      </aside>
    </>
  );
}
