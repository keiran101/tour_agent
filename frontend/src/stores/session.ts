"use client";

import { create } from "zustand";
import type { SessionListItem, TripResponse } from "@/lib/types";

interface SessionState {
  sessions: SessionListItem[];
  trips: TripResponse[];
  activeSessionId: string | null;

  setSessions: (sessions: SessionListItem[]) => void;
  setTrips: (trips: TripResponse[]) => void;
  setActiveSession: (id: string | null) => void;
  addSession: (session: SessionListItem) => void;
  removeSession: (id: string) => void;
  renameSession: (id: string, name: string) => void;
}

export const useSessionStore = create<SessionState>()((set) => ({
  sessions: [],
  trips: [],
  activeSessionId: null,

  setSessions: (sessions) => set({ sessions }),
  setTrips: (trips) => set({ trips }),
  setActiveSession: (activeSessionId) => set({ activeSessionId }),

  addSession: (session) =>
    set((state) => ({ sessions: [session, ...state.sessions] })),

  removeSession: (id) =>
    set((state) => ({
      sessions: state.sessions.filter((s) => s.session_id !== id),
      activeSessionId: state.activeSessionId === id ? null : state.activeSessionId,
    })),

  renameSession: (id, name) =>
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.session_id === id ? { ...s, name } : s,
      ),
    })),
}));
