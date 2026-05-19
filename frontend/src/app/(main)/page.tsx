"use client";

import { useEffect, useRef, useCallback } from "react";
import { MapPin } from "lucide-react";
import { useChatStore } from "@/stores/chat";
import { useAuthStore } from "@/stores/auth";
import { streamChat } from "@/lib/sse";
import type { SSEEvent, BuilderAction } from "@/lib/types";
import MessageBubble from "@/components/chat/message-bubble";
import TypingIndicator from "@/components/chat/typing-indicator";
import ChatInput from "@/components/chat/chat-input";
import PhaseIndicator from "@/components/phase-indicator";

export default function ChatPage() {
  const {
    messages,
    isLoading,
    streamingContent,
    addMessage,
    setLoading,
    setStreamingContent,
    appendStreamingContent,
    setPhase,
  } = useChatStore();
  const sessionToken = useAuthStore((s) => s.sessionToken);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent, isLoading, scrollToBottom]);

  function handleSend(content: string, builderAction?: BuilderAction) {
    if (!sessionToken || isLoading) return;

    addMessage({ role: "user", content });
    setLoading(true);
    setStreamingContent("");

    abortRef.current = streamChat(
      [{ role: "user", content }],
      sessionToken,
      {
        onEvent(event: SSEEvent) {
          switch (event.type) {
            case "answer":
              appendStreamingContent(event.content);
              break;
            case "gathering":
              addMessage({
                role: "assistant",
                content: event.content,
                questions: event.questions,
              });
              setPhase("gathering");
              break;
            case "builder":
              addMessage({
                role: "assistant",
                content: event.content,
                builder: { layer: event.layer, data: event.data },
              });
              setPhase(event.layer);
              break;
            case "error":
              addMessage({
                role: "assistant",
                content: `出错了: ${event.message}`,
              });
              break;
          }
        },
        onDone() {
          const finalContent = useChatStore.getState().streamingContent;
          if (finalContent) {
            addMessage({ role: "assistant", content: finalContent });
            setStreamingContent("");
          }
          setLoading(false);
        },
        onError(error) {
          addMessage({
            role: "assistant",
            content: `连接失败: ${error.message}`,
          });
          setLoading(false);
          setStreamingContent("");
        },
      },
      builderAction,
    );
  }

  const hasMessages = messages.length > 0;

  return (
    <div className="relative flex flex-1 flex-col overflow-hidden">
      <PhaseIndicator />
      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {!hasMessages ? (
          <div className="flex h-full items-center justify-center">
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-primary-subtle">
                <MapPin className="h-8 w-8 text-primary" />
              </div>
              <h2 className="text-xl font-semibold">开始规划你的旅行</h2>
              <p className="max-w-sm text-sm text-muted-foreground">
                告诉我你想去哪里、玩几天，我来帮你定制专属行程
              </p>
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-4 px-4 py-6">
            {messages.map((msg, i) => {
              const isLastAssistant =
                msg.role === "assistant" &&
                !messages.slice(i + 1).some((m) => m.role === "assistant");
              return (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onSendMessage={handleSend}
                  isLastAssistant={isLastAssistant}
                />
              );
            })}

            {streamingContent && (
              <MessageBubble
                message={{
                  id: "streaming",
                  role: "assistant",
                  content: streamingContent,
                  timestamp: Date.now(),
                }}
              />
            )}

            {isLoading && !streamingContent && <TypingIndicator />}
          </div>
        )}
      </div>

      {/* Input */}
      <ChatInput onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
