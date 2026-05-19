"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ChevronDown, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import POICard from "./poi-card";
import type { SelectPOIsPayload, BuilderAction } from "@/lib/types";

interface SelectPOIsProps {
  data: SelectPOIsPayload;
  onSubmit: (text: string, action?: BuilderAction) => void;
  disabled?: boolean;
}

export default function SelectPOIs({ data, onSubmit, disabled }: SelectPOIsProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showAlternatives, setShowAlternatives] = useState(false);

  function togglePOI(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleSubmit() {
    const ids = [...selectedIds];
    const allPOIs = [...data.recommended, ...data.alternatives];
    const names = allPOIs
      .filter((p) => selectedIds.has(p.id))
      .map((p) => p.name);
    if (names.length > 0) {
      onSubmit(`我选这几个：${names.join("、")}`, {
        action: "advance",
        selected_ids: ids,
      });
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="max-w-[900px] space-y-6"
    >
      {/* Recommended */}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <div className="h-6 w-1 rounded-full bg-primary" />
          <h3 className="text-lg font-semibold">推荐景点</h3>
        </div>
        <motion.div
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
          initial="hidden"
          animate="visible"
          variants={{ visible: { transition: { staggerChildren: 0.06 } } }}
        >
          {data.recommended.map((poi) => (
            <motion.div
              key={poi.id}
              variants={{
                hidden: { opacity: 0, y: 20 },
                visible: { opacity: 1, y: 0 },
              }}
              transition={{ duration: 0.4, ease: "easeOut" }}
            >
              <POICard
                poi={poi}
                selected={selectedIds.has(poi.id)}
                onToggle={togglePOI}
              />
            </motion.div>
          ))}
        </motion.div>
      </div>

      {/* Alternatives */}
      {data.alternatives.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowAlternatives(!showAlternatives)}
            className="mb-3 flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
          >
            <div className="h-6 w-1 rounded-full bg-muted-foreground/30" />
            <span>备选景点 ({data.alternatives.length}个)</span>
            <ChevronDown
              className={`h-4 w-4 transition-transform ${showAlternatives ? "rotate-180" : ""}`}
            />
          </button>
          {showAlternatives && (
            <motion.div
              className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
              initial="hidden"
              animate="visible"
              variants={{ visible: { transition: { staggerChildren: 0.06 } } }}
            >
              {data.alternatives.map((poi) => (
                <motion.div
                  key={poi.id}
                  variants={{
                    hidden: { opacity: 0, y: 20 },
                    visible: { opacity: 1, y: 0 },
                  }}
                  transition={{ duration: 0.4, ease: "easeOut" }}
                >
                  <POICard
                    poi={poi}
                    selected={selectedIds.has(poi.id)}
                    onToggle={togglePOI}
                  />
                </motion.div>
              ))}
            </motion.div>
          )}
        </div>
      )}

      {/* Submit */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          已选 {selectedIds.size} 个景点
        </span>
        <Button
          disabled={selectedIds.size === 0 || disabled}
          onClick={handleSubmit}
        >
          确认选择
          <Send className="ml-1.5 h-4 w-4" />
        </Button>
      </div>
    </motion.div>
  );
}
