"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, X, Lightbulb, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DAY_COLORS } from "@/lib/poi-utils";
import type { GroupDaysPayload, BuilderAction } from "@/lib/types";

interface SortableItemProps {
  id: string;
  name: string;
  onRemove?: () => void;
}

function SortableItem({ id, name, onRemove }: SortableItemProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-2 rounded-lg border bg-card px-3 py-2.5 text-sm ${
        isDragging
          ? "z-10 border-primary shadow-lg opacity-90 scale-[1.02]"
          : "border-border-subtle"
      }`}
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab text-muted-foreground hover:text-foreground active:cursor-grabbing"
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <span className="flex-1 truncate font-medium">{name}</span>
      {onRemove && (
        <button
          onClick={onRemove}
          className="text-muted-foreground hover:text-destructive"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

interface DayGroupProps {
  data: GroupDaysPayload;
  poiNames: Record<string, string>;
  onSubmit: (text: string, action?: BuilderAction) => void;
  disabled?: boolean;
}

export default function DayGroup({ data, poiNames, onSubmit, disabled }: DayGroupProps) {
  const [days, setDays] = useState(data.days);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    setDays((prev) => {
      const next = prev.map((d) => ({ ...d, items: [...d.items] }));

      let srcDayIdx = -1;
      let srcItemIdx = -1;
      for (let i = 0; i < next.length; i++) {
        const idx = next[i].items.indexOf(activeId);
        if (idx !== -1) {
          srcDayIdx = i;
          srcItemIdx = idx;
          break;
        }
      }
      if (srcDayIdx === -1) return prev;

      let dstDayIdx = -1;
      let dstItemIdx = -1;
      for (let i = 0; i < next.length; i++) {
        const idx = next[i].items.indexOf(overId);
        if (idx !== -1) {
          dstDayIdx = i;
          dstItemIdx = idx;
          break;
        }
      }
      if (dstDayIdx === -1) return prev;

      next[srcDayIdx].items.splice(srcItemIdx, 1);
      next[dstDayIdx].items.splice(dstItemIdx, 0, activeId);

      return next;
    });
  }

  function handleSubmit() {
    onSubmit("确认这个分组方案", {
      action: "advance",
      day_groups: days,
    });
  }

  const allItems = days.flatMap((d) => d.items);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="max-w-[900px] space-y-4"
    >
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <div className="flex gap-4 overflow-x-auto pb-2">
          {days.map((day, i) => {
            const color = DAY_COLORS[i % DAY_COLORS.length];
            return (
              <div
                key={day.day}
                className="min-w-[260px] flex-1 rounded-xl border border-border-subtle bg-card shadow-sm"
              >
                {/* Header */}
                <div className={`rounded-t-xl px-4 py-3 ${color.bg}`}>
                  <h4 className={`font-semibold ${color.text}`}>
                    第{day.day}天 · {day.theme}
                  </h4>
                  {day.reason && (
                    <p className="mt-1 text-xs text-muted-foreground">{day.reason}</p>
                  )}
                </div>

                {/* Items */}
                <div className="space-y-2 p-3">
                  <SortableContext items={day.items} strategy={verticalListSortingStrategy}>
                    {day.items.map((id) => (
                      <SortableItem
                        key={id}
                        id={id}
                        name={poiNames[id] ?? id}
                      />
                    ))}
                  </SortableContext>
                  {day.items.length === 0 && (
                    <div className="rounded-lg border-2 border-dashed border-border py-4 text-center text-xs text-muted-foreground">
                      拖拽景点到这里
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </DndContext>

      {/* Suggestion */}
      {data.suggestion && (
        <div className="flex items-start gap-2 rounded-lg bg-info/5 px-4 py-3 text-sm text-muted-foreground">
          <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-info" />
          <span>{data.suggestion}</span>
        </div>
      )}

      {/* Submit */}
      <div className="flex justify-end">
        <Button disabled={disabled} onClick={handleSubmit}>
          确认分组
          <Send className="ml-1.5 h-4 w-4" />
        </Button>
      </div>
    </motion.div>
  );
}
