"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Question } from "@/lib/types";

interface QuestionCardProps {
  questions: Question[];
  onSubmit: (text: string) => void;
  disabled?: boolean;
}

export default function QuestionCard({ questions, onSubmit, disabled }: QuestionCardProps) {
  const [selections, setSelections] = useState<Record<string, string[]>>({});
  const [freeText, setFreeText] = useState<Record<string, string>>({});

  function toggleOption(questionId: string, option: string, allowMultiple: boolean) {
    setSelections((prev) => {
      const current = prev[questionId] ?? [];
      if (allowMultiple) {
        return {
          ...prev,
          [questionId]: current.includes(option)
            ? current.filter((o) => o !== option)
            : [...current, option],
        };
      }
      return {
        ...prev,
        [questionId]: current.includes(option) ? [] : [option],
      };
    });
  }

  function handleSubmit() {
    const parts: string[] = [];

    for (const q of questions) {
      if (q.options.length > 0) {
        const selected = selections[q.id] ?? [];
        if (selected.length > 0) {
          parts.push(`${q.text}：${selected.join("、")}`);
        }
      } else {
        const text = freeText[q.id]?.trim();
        if (text) {
          parts.push(`${q.text}：${text}`);
        }
      }
    }

    if (parts.length > 0) {
      onSubmit(parts.join("；"));
    }
  }

  const hasAnySelection = questions.some((q) => {
    if (q.options.length > 0) {
      return (selections[q.id] ?? []).length > 0;
    }
    return (freeText[q.id] ?? "").trim().length > 0;
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="max-w-[600px] space-y-5 rounded-xl border border-border-subtle bg-card p-5 shadow-sm"
    >
      {questions.map((q) => (
        <div key={q.id} className="space-y-3">
          <div>
            <p className="text-sm font-semibold text-foreground">{q.text}</p>
            {q.allow_multiple && q.options.length > 0 && (
              <p className="text-xs text-muted-foreground">(可多选)</p>
            )}
          </div>

          {q.options.length > 0 ? (
            <motion.div
              className="flex flex-wrap gap-2"
              initial="hidden"
              animate="visible"
              variants={{ visible: { transition: { staggerChildren: 0.05 } } }}
            >
              {q.options.map((opt) => {
                const selected = (selections[q.id] ?? []).includes(opt);
                return (
                  <motion.button
                    key={opt}
                    type="button"
                    disabled={disabled}
                    onClick={() => toggleOption(q.id, opt, q.allow_multiple)}
                    variants={{
                      hidden: { opacity: 0, scale: 0.8, y: 8 },
                      visible: { opacity: 1, scale: 1, y: 0 },
                    }}
                    whileTap={{ scale: 0.95 }}
                    className={`rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                      selected
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-card text-foreground hover:border-primary/40 hover:bg-primary-subtle"
                    }`}
                  >
                    {opt}
                  </motion.button>
                );
              })}
            </motion.div>
          ) : (
            <input
              type="text"
              placeholder="请输入..."
              value={freeText[q.id] ?? ""}
              onChange={(e) =>
                setFreeText((prev) => ({ ...prev, [q.id]: e.target.value }))
              }
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSubmit();
              }}
              disabled={disabled}
              className="w-full rounded-lg border border-border bg-surface-sunken px-3 py-2.5 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/25"
            />
          )}
        </div>
      ))}

      <div className="flex justify-end">
        <Button
          size="sm"
          disabled={!hasAnySelection || disabled}
          onClick={handleSubmit}
        >
          确认选择
          <Send className="ml-1.5 h-3.5 w-3.5" />
        </Button>
      </div>
    </motion.div>
  );
}
