"use client";

import { motion } from "framer-motion";
import { MapPin, Calendar, Wallet, Check, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ConfirmPanelProps {
  onConfirm: () => void;
  onBack: () => void;
  disabled?: boolean;
}

export default function ConfirmPanel({ onConfirm, onBack, disabled }: ConfirmPanelProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="max-w-[600px] rounded-xl border border-border-subtle bg-card p-6 shadow-sm"
    >
      <h3 className="text-lg font-semibold">确认行程</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        行程已规划完成，确认后将保存到你的行程列表中。
      </p>

      <div className="mt-6 flex gap-3">
        <Button variant="outline" onClick={onBack} disabled={disabled}>
          <ArrowLeft className="mr-1.5 h-4 w-4" />
          返回修改
        </Button>
        <Button
          onClick={onConfirm}
          disabled={disabled}
          className="bg-success text-success-foreground hover:bg-success/90"
        >
          <Check className="mr-1.5 h-4 w-4" />
          确认保存行程
        </Button>
      </div>
    </motion.div>
  );
}
