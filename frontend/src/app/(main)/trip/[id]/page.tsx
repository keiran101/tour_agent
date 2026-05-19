"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  MapPin,
  Calendar,
  ArrowLeft,
  Loader2,
  Clock,
  Footprints,
  Car,
  Bus,
  Lightbulb,
  Wallet,
} from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth";
import { getTrip } from "@/lib/api";
import type { TripResponse, DayPlan } from "@/lib/types";

const DAY_COLORS = [
  "text-day-1 bg-day-1/10",
  "text-day-2 bg-day-2/10",
  "text-day-3 bg-day-3/10",
  "text-day-4 bg-day-4/10",
  "text-day-5 bg-day-5/10",
];

const SLOT_LABELS: Record<string, string> = {
  morning: "上午",
  lunch: "午餐",
  afternoon: "下午",
  dinner: "晚餐",
  evening: "晚间",
};

function TransportIcon({ tip }: { tip: string }) {
  if (tip.includes("步行") || tip.includes("走")) return <Footprints className="h-3.5 w-3.5" />;
  if (tip.includes("打车") || tip.includes("出租")) return <Car className="h-3.5 w-3.5" />;
  if (tip.includes("公交") || tip.includes("地铁")) return <Bus className="h-3.5 w-3.5" />;
  return <Car className="h-3.5 w-3.5" />;
}

function DayTimeline({ day, colorClass }: { day: DayPlan; colorClass: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="space-y-1"
    >
      <div className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold ${colorClass}`}>
        第{day.day}天 · {day.theme}
      </div>

      <div className="relative ml-4 border-l-2 border-border pl-6 pt-2">
        {day.activities.map((act, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: i * 0.1, ease: "easeOut" }}
            className="relative pb-6 last:pb-0"
          >
            <div className="absolute -left-[31px] top-1 h-3 w-3 rounded-full border-2 border-border bg-card" />
            <div className="rounded-lg border border-border-subtle bg-card p-4 shadow-xs">
              <div className="flex items-start justify-between gap-2">
                <h4 className="font-medium">{act.name}</h4>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {SLOT_LABELS[act.time_slot] ?? act.time_slot}
                </span>
              </div>
              {act.description && (
                <p className="mt-1 text-sm text-muted-foreground">{act.description}</p>
              )}
              <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {act.duration_minutes}分钟
                </span>
                {act.location && (
                  <span className="flex items-center gap-1">
                    <MapPin className="h-3 w-3" />
                    {act.location}
                  </span>
                )}
              </div>
              {act.tips && (
                <p className="mt-2 text-xs text-info italic">{act.tips}</p>
              )}
            </div>

            {day.transport_tips && i < day.activities.length - 1 && (
              <div className="ml-2 mt-2 mb-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                <TransportIcon tip={day.transport_tips} />
                <span>{day.transport_tips}</span>
              </div>
            )}
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}

export default function TripDetailPage() {
  const params = useParams();
  const router = useRouter();
  const userToken = useAuthStore((s) => s.userToken);
  const [trip, setTrip] = useState<TripResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!userToken || !params.id) return;
    getTrip(params.id as string, userToken)
      .then(setTrip)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [userToken, params.id]);

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !trip) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="space-y-3 text-center">
          <p className="text-muted-foreground">{error || "行程未找到"}</p>
          <Button variant="outline" onClick={() => router.push("/")}>
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            返回
          </Button>
        </div>
      </div>
    );
  }

  const { itinerary } = trip;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-6">
        {/* Header */}
        <div className="mb-8">
          <Button
            variant="ghost"
            size="sm"
            className="mb-4 text-muted-foreground"
            onClick={() => router.push("/")}
          >
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            返回
          </Button>

          <h1 className="text-2xl font-bold">{trip.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <MapPin className="h-4 w-4" />
              {trip.destination}
            </span>
            <span className="flex items-center gap-1">
              <Calendar className="h-4 w-4" />
              {itinerary.total_days}天
            </span>
            {itinerary.budget_estimate && (
              <span className="flex items-center gap-1">
                <Wallet className="h-4 w-4" />
                {itinerary.budget_estimate}
              </span>
            )}
          </div>
        </div>

        {/* Timeline */}
        <div className="space-y-8">
          {itinerary.days.map((day, i) => (
            <DayTimeline
              key={day.day}
              day={day}
              colorClass={DAY_COLORS[i % DAY_COLORS.length]}
            />
          ))}
        </div>

        {/* Tips */}
        {itinerary.tips.length > 0 && (
          <div className="mt-8 rounded-xl bg-info/5 p-5">
            <h3 className="mb-3 flex items-center gap-2 font-semibold text-info">
              <Lightbulb className="h-4 w-4" />
              小贴士
            </h3>
            <ul className="space-y-1.5 text-sm text-muted-foreground">
              {itinerary.tips.map((tip, i) => (
                <li key={i}>• {tip}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
