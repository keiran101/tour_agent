"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  userToken: string | null;
  userEmail: string | null;
  sessionId: string | null;
  sessionToken: string | null;

  setUser: (token: string, email: string) => void;
  setSession: (sessionId: string, token: string) => void;
  clearSession: () => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      userToken: null,
      userEmail: null,
      sessionId: null,
      sessionToken: null,

      setUser: (token, email) => set({ userToken: token, userEmail: email }),

      setSession: (sessionId, token) =>
        set({ sessionId, sessionToken: token }),

      clearSession: () => set({ sessionId: null, sessionToken: null }),

      logout: () =>
        set({
          userToken: null,
          userEmail: null,
          sessionId: null,
          sessionToken: null,
        }),
    }),
    { name: "tour-agent-auth" },
  ),
);
