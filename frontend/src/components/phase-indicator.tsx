"use client";

import { motion } from "framer-motion";
import { useChatStore } from "@/stores/chat";
import type { BuilderPhase } from "@/lib/types";

const PHASES: { key: BuilderPhase; label: string }[] = [
  { key: "gathering", label: "收集需求" },
  { key: "select_pois", label: "选景点" },
  { key: "group_days", label: "分天" },
  { key: "arrange", label: "安排" },
  { key: "confirm", label: "确认" },
];

export default function PhaseIndicator() {
  const phase = useChatStore((s) => s.phase);

  if (!phase || phase === "chat") return null;

  const currentIdx = PHASES.findIndex((p) => p.key === phase);

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="pointer-events-none absolute inset-x-0 top-3 z-10 flex justify-center"
    >
      <div className="pointer-events-auto flex items-center gap-1.5 rounded-full border border-border-subtle bg-surface-glass px-4 py-2 shadow-sm backdrop-blur-xl">
        {PHASES.map((p, i) => {
          const isActive = i === currentIdx;
          const isDone = i < currentIdx;
          return (
            <div key={p.key} className="flex items-center gap-1.5">
              {i > 0 && (
                <div
                  className={`h-px w-4 transition-colors ${
                    isDone ? "bg-primary" : "bg-border"
                  }`}
                />
              )}
              <div className="flex items-center gap-1">
                <div className="relative">
                  <div
                    className={`h-2.5 w-2.5 rounded-full transition-colors ${
                      isActive
                        ? "bg-primary"
                        : isDone
                          ? "bg-primary/60"
                          : "bg-border"
                    }`}
                  />
                  {isActive && (
                    <motion.div
                      className="absolute inset-0 rounded-full bg-primary/40"
                      animate={{ scale: [1, 1.8, 1] }}
                      transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                    />
                  )}
                </div>
                <span
                  className={`hidden text-xs font-medium sm:inline ${
                    isActive
                      ? "text-primary"
                      : isDone
                        ? "text-foreground"
                        : "text-muted-foreground"
                  }`}
                >
                  {p.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
