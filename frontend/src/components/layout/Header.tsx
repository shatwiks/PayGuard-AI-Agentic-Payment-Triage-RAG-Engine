"use client";

import React from "react";
import { useAuth } from "@/context/AuthContext";
import { Menu, LogOut, User, ShieldCheck } from "lucide-react";

interface HeaderProps {
  onToggleSidebar: () => void;
  title?: string;
}

export function Header({ onToggleSidebar, title }: HeaderProps) {
  const { user, logout } = useAuth();

  const roleLabels: Record<string, string> = {
    admin: "Admin",
    compliance_analyst: "Compliance Analyst",
    support_agent: "Support Operator",
  };

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 shadow-2xs">
      <div className="flex items-center space-x-3">
        <button
          onClick={onToggleSidebar}
          className="md:hidden p-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100"
          aria-label="Toggle Navigation"
        >
          <Menu className="w-5 h-5" />
        </button>
        {title && <h1 className="text-lg font-semibold text-slate-900">{title}</h1>}
      </div>

      <div className="flex items-center space-x-4">
        {user ? (
          <div className="flex items-center space-x-3">
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-sm font-medium text-slate-800 leading-tight">
                {user.full_name || user.email}
              </span>
              <span className="text-[11px] text-slate-500 flex items-center justify-end">
                <ShieldCheck className="w-3 h-3 text-blue-500 mr-1" />
                {roleLabels[user.role] || user.role}
              </span>
            </div>
            <div className="w-9 h-9 rounded-full bg-slate-100 border border-slate-300 text-slate-600 flex items-center justify-center font-semibold text-xs">
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
              onClick={logout}
              title="Sign Out"
              className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="h-8 w-24 bg-slate-100 animate-pulse rounded-md" />
        )}
      </div>
    </header>
  );
}
