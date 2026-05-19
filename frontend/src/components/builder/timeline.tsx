"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Clock,
  Footprints,
  Car,
  Bus,
  Lightbulb,
  Wallet,
  Send,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { DAY_COLORS } from "@/lib/poi-utils";
import type { ArrangePayload, BuilderAction, DaySchedule } from "@/lib/types";

function TransportIcon({ text }: { text: string }) {
  if (text.includes("步行") || text.includes("走")) return <Footprints className="h-3.5 w-3.5" />;
  if (text.includes("公交") || text.includes("地铁")) return <Bus className="h-3.5 w-3.5" />;
  return <Car className="h-3.5 w-3.5" />;
}

function DayTimeline({ day, colorIdx }: { day: DaySchedule; colorIdx: number }) {
  const color = DAY_COLORS[colorIdx % DAY_COLORS.length];

  return (
    <div className="relative ml-4 border-l-2 border-border pl-6">
      {day.activities.map((act, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: i * 0.12, ease: "easeOut" }}
          className="relative pb-6 last:pb-0"
        >
          {/* Dot */}
          <div className={`absolute -left-[31px] top-1.5 h-3 w-3 rounded-full border-2 bg-card ${color.border}`} />

          {/* Time label */}
          <span className="mb-1 block font-mono text-xs text-muted-foreground">
            {act.time}
          </span>

          {/* Activity card */}
          <div className="rounded-lg border border-border-subtle bg-card p-4 shadow-xs">
            <h4 className="font-medium">{act.name}</h4>
          </div>

          {/* Transport */}
          {act.transport_to_next && i < day.activities.length - 1 && (
            <div className="ml-2 mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
              <TransportIcon text={act.transport_to_next} />
              <span>{act.transport_to_next}</span>
            </div>
          )}
        </motion.div>
      ))}
    </div>
  );
}

interface TimelineProps {
  data: ArrangePayload;
  onSubmit?: (text: string, action?: BuilderAction) => void;
  disabled?: boolean;
}

export default function Timeline({ data, onSubmit, disabled }: TimelineProps) {
  const [activeDay, setActiveDay] = useState(0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="max-w-[700px] space-y-4"
    >
      {/* Day tabs */}
      {data.days.length > 1 && (
        <div className="flex gap-1 overflow-x-auto border-b border-border-subtle">
          {data.days.map((day, i) => {
            const color = DAY_COLORS[i % DAY_COLORS.length];
            const isActive = i === activeDay;
            return (
              <button
                key={day.day}
                onClick={() => setActiveDay(i)}
                className={`shrink-0 border-b-2 px-4 py-2.5 text-sm transition-colors ${
                  isActive
                    ? `${color.text} ${color.border} font-semibold`
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                第{day.day}天
                {day.theme && (
                  <span className="ml-1 text-xs opacity-70">{day.theme}</span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Timeline */}
      <DayTimeline day={data.days[activeDay]} colorIdx={activeDay} />

      {/* Tips */}
      {data.tips.length > 0 && (
        <div className="rounded-xl bg-info/5 p-4">
          <h4 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-info">
            <Lightbulb className="h-4 w-4" />
            小贴士
          </h4>
          <ul className="space-y-1 text-sm text-muted-foreground">
            {data.tips.map((tip, i) => (
              <li key={i}>• {tip}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Budget */}
      {data.budget_estimate && (
        <div className="flex items-center gap-2 rounded-xl bg-warning/5 px-4 py-3 text-sm">
          <Wallet className="h-4 w-4 text-warning" />
          <span className="font-medium">预估费用：{data.budget_estimate}</span>
        </div>
      )}

      {/* Confirm */}
      {onSubmit && (
        <div className="flex justify-end">
          <Button disabled={disabled} onClick={() => onSubmit("确认这个行程安排", { action: "advance" })}>
            确认安排
            <Send className="ml-1.5 h-4 w-4" />
          </Button>
        </div>
      )}
    </motion.div>
  );
}
