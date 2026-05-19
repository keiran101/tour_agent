"use client";

import { motion } from "framer-motion";
import {
  Landmark,
  UtensilsCrossed,
  Bed,
  ShoppingBag,
  Bike,
  Star,
  Clock,
  Wallet,
  Check,
  Lightbulb,
} from "lucide-react";
import type { POIOption, POICategory } from "@/lib/types";
import { CATEGORY_CONFIG } from "@/lib/poi-utils";

const CATEGORY_ICONS: Record<POICategory, React.ReactNode> = {
  attraction: <Landmark className="h-5 w-5" />,
  restaurant: <UtensilsCrossed className="h-5 w-5" />,
  hotel: <Bed className="h-5 w-5" />,
  shopping: <ShoppingBag className="h-5 w-5" />,
  activity: <Bike className="h-5 w-5" />,
};

interface POICardProps {
  poi: POIOption;
  selected: boolean;
  onToggle: (id: string) => void;
}

export default function POICard({ poi, selected, onToggle }: POICardProps) {
  const cat = CATEGORY_CONFIG[poi.category];

  return (
    <motion.button
      type="button"
      onClick={() => onToggle(poi.id)}
      whileTap={{ scale: 0.98 }}
      className={`group relative w-full rounded-xl border p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md ${
        selected
          ? "border-primary bg-primary-subtle shadow-primary/10"
          : "border-border-subtle bg-card hover:border-border"
      }`}
    >
      {/* Checkbox */}
      <div
        className={`absolute right-4 top-4 flex h-5 w-5 items-center justify-center rounded transition-colors ${
          selected
            ? "bg-primary text-primary-foreground"
            : "border-2 border-border"
        }`}
      >
        {selected && (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 500, damping: 25 }}
          >
            <Check className="h-3.5 w-3.5" />
          </motion.div>
        )}
      </div>

      {/* Category icon + name */}
      <div className="flex items-start gap-3 pr-8">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${cat.bgClass} ${cat.colorClass}`}>
          {CATEGORY_ICONS[poi.category]}
        </div>
        <div className="min-w-0">
          <h4 className="font-medium leading-tight">{poi.name}</h4>
          <span className={`text-xs font-medium ${cat.colorClass}`}>{cat.label}</span>
        </div>
      </div>

      {/* Brief */}
      <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">{poi.brief}</p>

      {/* Reason */}
      {poi.reason && (
        <div className="mt-3 flex items-start gap-1.5 rounded-md bg-info/5 px-3 py-2 text-xs text-muted-foreground">
          <Lightbulb className="mt-0.5 h-3 w-3 shrink-0 text-info" />
          <span>{poi.reason}</span>
        </div>
      )}

      {/* Meta row */}
      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        {poi.meta.rating != null && (
          <span className="flex items-center gap-1">
            <Star className="h-3 w-3 text-amber-500" />
            {poi.meta.rating}
          </span>
        )}
        {poi.meta.price && (
          <span className="flex items-center gap-1">
            <Wallet className="h-3 w-3" />
            {poi.meta.price}
          </span>
        )}
        {poi.meta.duration && (
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {poi.meta.duration}
          </span>
        )}
      </div>
    </motion.button>
  );
}
