"use client";

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { useAuth } from "@/context/AuthContext";

const STANDALONE_ROUTES = ["/welcome", "/login", "/register", "/privacy", "/terms"];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const pathname = usePathname();
  const { isLoading, isAuthenticated } = useAuth();

  const isStandalonePage = STANDALONE_ROUTES.some((route) =>
    pathname.startsWith(route)
  );

  // Standalone public routes (Landing page, Login, Register, Legal notices)
  if (isStandalonePage) {
    return <div className="min-h-[100dvh] bg-[#0B0D0F] text-[#F3F5F7]">{children}</div>;
  }

  // Loading state during initial auth token verification
  if (isLoading) {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center bg-[#0B0D0F] text-[#F3F5F7]">
        <div className="flex flex-col items-center space-y-3">
          <div className="w-7 h-7 border-2 border-[#C6F36A] border-t-transparent rounded-full animate-spin" />
          <p className="text-xs font-mono text-[#9BA5B0]">
            Verifying PayGuard AI session...
          </p>
        </div>
      </div>
    );
  }

  // Unauthenticated root `/` renders the public LandingPage directly without dashboard shell
  if (pathname === "/" && !isAuthenticated) {
    return <div className="min-h-[100dvh] bg-[#0B0D0F] text-[#F3F5F7]">{children}</div>;
  }

  // Prevent flashing protected shell when unauthenticated on protected routes
  if (!isAuthenticated) {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center bg-[#0B0D0F] text-[#9BA5B0] text-xs font-mono">
        Redirecting to operator sign-in...
      </div>
    );
  }

  return (
    <div className="min-h-[100dvh] flex bg-[#0B0D0F] text-[#F3F5F7]">
      <Sidebar
        isOpen={sidebarOpen}
        setIsOpen={setSidebarOpen}
        isCollapsed={sidebarCollapsed}
        setIsCollapsed={setSidebarCollapsed}
      />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header onToggleSidebar={() => setSidebarOpen((prev) => !prev)} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 max-w-[1440px] w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
