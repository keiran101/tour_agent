"use client";

import { motion } from "framer-motion";
import type { ChatMessage } from "@/stores/chat";
import type { BuilderAction } from "@/lib/types";
import QuestionCard from "@/components/gathering/question-card";
import BuilderPanel from "@/components/builder/builder-panel";

interface MessageBubbleProps {
  message: ChatMessage;
  onSendMessage?: (text: string, builderAction?: BuilderAction) => void;
  isLastAssistant?: boolean;
}

export default function MessageBubble({
  message,
  onSendMessage,
  isLastAssistant,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const hasQuestions = message.questions && message.questions.length > 0;
  const hasBuilder = !!message.builder;
  const isInteractive = isLastAssistant && !!onSendMessage;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={`flex flex-col ${isUser ? "items-end" : "items-start"} gap-3`}
    >
      {message.content && (
        <div
          className={`max-w-[85%] whitespace-pre-wrap px-4 py-3 text-base leading-relaxed ${
            isUser
              ? "rounded-[12px_12px_4px_12px] bg-primary text-primary-foreground shadow-sm"
              : "rounded-[12px_12px_12px_4px] border border-border-subtle bg-card text-card-foreground shadow-xs"
          }`}
        >
          {message.content}
        </div>
      )}

      {hasQuestions && onSendMessage && (
        <QuestionCard
          questions={message.questions!}
          onSubmit={onSendMessage}
          disabled={!isInteractive}
        />
      )}

      {hasBuilder && onSendMessage && (
        <BuilderPanel
          builder={message.builder!}
          onSendMessage={onSendMessage}
          disabled={!isInteractive}
        />
      )}
    </motion.div>
  );
}
