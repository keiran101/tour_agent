"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Menu } from "lucide-react";
import { useAuthStore } from "@/stores/auth";
import Sidebar from "@/components/sidebar";

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const userToken = useAuthStore((s) => s.userToken);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!userToken) {
      router.replace("/login");
    }
  }, [userToken, router]);

  if (!userToken) return null;

  return (
    <div className="flex h-dvh overflow-hidden">
      {/* Desktop sidebar */}
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="relative z-50 h-full w-[280px] animate-in slide-in-from-left duration-200">
            <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile header */}
        <div className="flex h-12 items-center gap-3 border-b border-border-subtle px-4 lg:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-muted-foreground hover:text-foreground"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="text-sm font-semibold">如途</span>
        </div>
        {children}
      </main>
    </div>
  );
}
