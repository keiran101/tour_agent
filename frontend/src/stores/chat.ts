"use client";

import { create } from "zustand";
import type {
  Message,
  Question,
  BuilderResponse,
  BuilderPhase,
  SessionDetail,
} from "@/lib/types";

export interface ChatMessage extends Message {
  id: string;
  timestamp: number;
  questions?: Question[];
  builder?: BuilderResponse;
}

interface ChatState {
  messages: ChatMessage[];
  phase: BuilderPhase;
  isLoading: boolean;
  streamingContent: string;

  addMessage: (msg: Omit<ChatMessage, "id" | "timestamp">) => void;
  updateLastAssistant: (update: Partial<ChatMessage>) => void;
  setPhase: (phase: BuilderPhase) => void;
  setLoading: (loading: boolean) => void;
  setStreamingContent: (content: string) => void;
  appendStreamingContent: (chunk: string) => void;
  clearMessages: () => void;
  loadSession: (detail: SessionDetail) => void;
}

let msgCounter = 0;

export const useChatStore = create<ChatState>()((set) => ({
  messages: [],
  phase: "chat",
  isLoading: false,
  streamingContent: "",

  addMessage: (msg) =>
    set((state) => ({
      messages: [
        ...state.messages,
        { ...msg, id: `msg-${++msgCounter}`, timestamp: Date.now() },
      ],
    })),

  updateLastAssistant: (update) =>
    set((state) => {
      const msgs = [...state.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === "assistant") {
          msgs[i] = { ...msgs[i], ...update };
          break;
        }
      }
      return { messages: msgs };
    }),

  setPhase: (phase) => set({ phase }),
  setLoading: (isLoading) => set({ isLoading }),
  setStreamingContent: (streamingContent) => set({ streamingContent }),
  appendStreamingContent: (chunk) =>
    set((state) => ({ streamingContent: state.streamingContent + chunk })),
  clearMessages: () => set({ messages: [], phase: "chat", streamingContent: "" }),

  loadSession: (detail) => {
    const msgs: ChatMessage[] = detail.messages.map((m) => ({
      role: m.role,
      content: m.content,
      questions: m.questions,
      builder: m.builder,
      id: `msg-${++msgCounter}`,
      timestamp: Date.now(),
    }));
    set({
      messages: msgs,
      phase: detail.phase ?? "gathering",
      streamingContent: "",
      isLoading: false,
    });
  },
}));
