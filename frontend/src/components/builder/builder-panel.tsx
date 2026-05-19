"use client";

import type { BuilderResponse, BuilderAction, SelectPOIsPayload, GroupDaysPayload, ArrangePayload } from "@/lib/types";
import { useChatStore } from "@/stores/chat";
import SelectPOIs from "./select-pois";
import DayGroup from "./day-group";
import Timeline from "./timeline";
import ConfirmPanel from "./confirm-panel";

interface BuilderPanelProps {
  builder: BuilderResponse;
  onSendMessage: (text: string, builderAction?: BuilderAction) => void;
  disabled?: boolean;
}

export default function BuilderPanel({ builder, onSendMessage, disabled }: BuilderPanelProps) {
  const messages = useChatStore((s) => s.messages);

  switch (builder.layer) {
    case "select_pois":
      return (
        <SelectPOIs
          data={builder.data as SelectPOIsPayload}
          onSubmit={onSendMessage}
          disabled={disabled}
        />
      );

    case "group_days": {
      const poiNames: Record<string, string> = {};
      for (const msg of messages) {
        if (msg.builder?.layer === "select_pois") {
          const payload = msg.builder.data as SelectPOIsPayload;
          for (const poi of [...payload.recommended, ...payload.alternatives]) {
            poiNames[poi.id] = poi.name;
          }
        }
      }
      return (
        <DayGroup
          data={builder.data as GroupDaysPayload}
          poiNames={poiNames}
          onSubmit={onSendMessage}
          disabled={disabled}
        />
      );
    }

    case "arrange":
      return (
        <Timeline
          data={builder.data as ArrangePayload}
          onSubmit={onSendMessage}
          disabled={disabled}
        />
      );

    case "confirm":
      return (
        <ConfirmPanel
          onConfirm={() => onSendMessage("就这样，帮我保存行程", { action: "advance" })}
          onBack={() => onSendMessage("我想重新调整", { action: "back" })}
          disabled={disabled}
        />
      );

    default:
      return null;
  }
}
