import type { SSEEvent, BuilderAction } from "./types";
import { getStreamUrl } from "./api";

export interface SSECallbacks {
  onEvent: (event: SSEEvent) => void;
  onDone: () => void;
  onError: (error: Error) => void;
}

export function streamChat(
  messages: { role: string; content: string }[],
  sessionToken: string,
  callbacks: SSECallbacks,
  builderAction?: BuilderAction,
): AbortController {
  const controller = new AbortController();

  const body: Record<string, unknown> = { messages };
  if (builderAction) body.builder_action = builderAction;

  fetch(getStreamUrl(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${sessionToken}`,
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail ?? `HTTP ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;

          const data = trimmed.slice(6);
          if (data === "[DONE]") {
            callbacks.onDone();
            return;
          }

          try {
            const event = JSON.parse(data) as SSEEvent;
            callbacks.onEvent(event);
          } catch {
            // skip malformed events
          }
        }
      }

      callbacks.onDone();
    })
    .catch((err) => {
      if (err instanceof DOMException && err.name === "AbortError") return;
      callbacks.onError(err instanceof Error ? err : new Error(String(err)));
    });

  return controller;
}
