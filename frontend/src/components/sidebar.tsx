"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  MapPin,
  Plus,
  MessageSquare,
  Map,
  LogOut,
  Menu,
  X,
  Pencil,
  Trash2,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth";
import { useSessionStore } from "@/stores/session";
import { useChatStore } from "@/stores/chat";
import {
  listSessions,
  listTrips,
  createSession,
  getSession,
  renameSession as renameSessionApi,
  deleteSession as deleteSessionApi,
} from "@/lib/api";
import type { TripStatus } from "@/lib/types";
import ThemeToggle from "@/components/theme-toggle";
import { SidebarSkeleton } from "@/components/skeleton-loader";

const STATUS_DOT: Record<TripStatus, string> = {
  draft: "bg-warning",
  confirmed: "bg-success",
  completed: "bg-muted-foreground",
};

interface SidebarProps {
  open?: boolean;
  onClose?: () => void;
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  const router = useRouter();
  const { userToken, setSession, logout } = useAuthStore();
  const {
    sessions,
    trips,
    activeSessionId,
    setSessions,
    setTrips,
    setActiveSession,
    addSession,
  } = useSessionStore();
  const clearMessages = useChatStore((s) => s.clearMessages);
  const loadSession = useChatStore((s) => s.loadSession);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");

  useEffect(() => {
    if (!userToken) return;
    Promise.all([
      listSessions(userToken).then((res) => setSessions(res)).catch(() => {}),
      listTrips(userToken).then((res) => setTrips(res.trips)).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [userToken, setSessions, setTrips]);

  async function handleNewChat() {
    if (!userToken) return;
    try {
      const res = await createSession(userToken);
      setSession(res.session_id, res.token.access_token);
      setActiveSession(res.session_id);
      addSession({
        status: "success",
        session_id: res.session_id,
        name: res.name,
        token: res.token,
      });
      clearMessages();
    } catch {
      // handled by global error
    }
  }

  async function handleSelectSession(sessionId: string) {
    if (sessionId === activeSessionId) return;
    const session = sessions.find((s) => s.session_id === sessionId);
    if (session) {
      setSession(session.session_id, session.token.access_token);
    }
    setActiveSession(sessionId);
    clearMessages();
    onClose?.();

    if (userToken) {
      try {
        const detail = await getSession(sessionId, userToken);
        loadSession(detail);
      } catch {
        // session detail load failed, stay with empty chat
      }
    }
  }

  async function handleRename(sessionId: string) {
    if (!userToken || !editName.trim()) return;
    try {
      await renameSessionApi(sessionId, editName.trim(), userToken);
      useSessionStore.getState().renameSession(sessionId, editName.trim());
    } catch {}
    setEditingId(null);
  }

  async function handleDelete(sessionId: string) {
    if (!userToken) return;
    try {
      await deleteSessionApi(sessionId, userToken);
      useSessionStore.getState().removeSession(sessionId);
      if (activeSessionId === sessionId) {
        clearMessages();
      }
    } catch {}
  }

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <aside className="flex h-dvh w-[280px] flex-col border-r border-border-subtle bg-surface-raised">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2 px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <MapPin className="h-4 w-4" />
        </div>
        <span className="text-lg font-bold tracking-tight">如途</span>
        {onClose && (
          <button
            onClick={onClose}
            className="ml-auto text-muted-foreground hover:text-foreground lg:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* New chat */}
      <div className="px-3 pb-2">
        <Button
          variant="outline"
          className="w-full justify-start gap-2 border-dashed text-muted-foreground hover:border-primary hover:bg-primary-subtle hover:text-primary"
          onClick={handleNewChat}
        >
          <Plus className="h-4 w-4" />
          新建对话
        </Button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2">
        <p className="px-2 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          对话记录
        </p>
        {loading ? (
          <SidebarSkeleton />
        ) : (
          <>
            <div className="space-y-0.5">
              {sessions.map((s) => (
                <div
                  key={s.session_id}
                  className={`group flex w-full items-center rounded-md text-sm transition-colors ${
                    activeSessionId === s.session_id
                      ? "border-l-[3px] border-primary bg-primary-subtle text-primary"
                      : "text-foreground hover:bg-surface-sunken"
                  }`}
                >
                  {editingId === s.session_id ? (
                    <div className="flex flex-1 items-center gap-1 px-3 py-1.5">
                      <input
                        autoFocus
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleRename(s.session_id);
                          if (e.key === "Escape") setEditingId(null);
                        }}
                        className="min-w-0 flex-1 rounded border border-border bg-card px-2 py-1 text-xs outline-none focus:border-ring"
                      />
                      <button
                        onClick={() => handleRename(s.session_id)}
                        className="text-primary hover:text-primary/80"
                      >
                        <Check className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ) : (
                    <>
                      <button
                        onClick={() => handleSelectSession(s.session_id)}
                        className="flex flex-1 items-center gap-2 px-3 py-2.5 text-left"
                      >
                        <MessageSquare className="h-4 w-4 shrink-0" />
                        <span className="truncate">{s.name || "新对话"}</span>
                      </button>
                      <div className="flex shrink-0 items-center gap-0.5 pr-2 opacity-0 transition-opacity group-hover:opacity-100">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingId(s.session_id);
                            setEditName(s.name || "");
                          }}
                          className="rounded p-1 text-muted-foreground hover:text-foreground"
                        >
                          <Pencil className="h-3 w-3" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(s.session_id);
                          }}
                          className="rounded p-1 text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
              {sessions.length === 0 && (
                <p className="px-3 py-4 text-center text-xs text-muted-foreground">
                  暂无对话
                </p>
              )}
            </div>

            {/* Trip list */}
            {trips.length > 0 && (
              <>
                <div className="mx-2 my-3 border-t border-border-subtle" />
                <p className="px-2 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  我的行程
                </p>
                <div className="space-y-0.5">
                  {trips.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => router.push(`/trip/${t.id}`)}
                      className="flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-left text-sm text-foreground transition-colors hover:bg-surface-sunken"
                    >
                      <Map className="h-4 w-4 shrink-0" />
                      <span className="flex-1 truncate">{t.title}</span>
                      <span
                        className={`h-2 w-2 rounded-full ${STATUS_DOT[t.status] ?? STATUS_DOT.draft}`}
                      />
                    </button>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-border-subtle px-4 py-3">
        <span className="truncate text-xs text-muted-foreground">
          {useAuthStore.getState().userEmail ?? ""}
        </span>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
            onClick={handleLogout}
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </aside>
  );
}
