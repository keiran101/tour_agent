"use client";

import { motion } from "framer-motion";

export default function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-1 rounded-[12px_12px_12px_4px] border border-border-subtle bg-card px-4 py-3 shadow-xs">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="block h-2 w-2 rounded-full bg-muted-foreground"
            animate={{ scale: [0.6, 1, 0.6], opacity: [0.4, 1, 0.4] }}
            transition={{
              duration: 1.4,
              repeat: Infinity,
              delay: i * 0.2,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>
    </div>
  );
}
