import type { POICategory } from "./types";

export const CATEGORY_CONFIG: Record<
  POICategory,
  { label: string; icon: string; colorClass: string; bgClass: string }
> = {
  attraction: {
    label: "景点",
    icon: "Landmark",
    colorClass: "text-poi-attraction",
    bgClass: "bg-poi-attraction-bg",
  },
  restaurant: {
    label: "餐厅",
    icon: "UtensilsCrossed",
    colorClass: "text-poi-restaurant",
    bgClass: "bg-poi-restaurant-bg",
  },
  hotel: {
    label: "住宿",
    icon: "Bed",
    colorClass: "text-poi-hotel",
    bgClass: "bg-poi-hotel-bg",
  },
  shopping: {
    label: "购物",
    icon: "ShoppingBag",
    colorClass: "text-poi-shopping",
    bgClass: "bg-poi-shopping-bg",
  },
  activity: {
    label: "活动",
    icon: "Bike",
    colorClass: "text-poi-activity",
    bgClass: "bg-poi-activity-bg",
  },
};

export const DAY_COLORS = [
  { text: "text-day-1", bg: "bg-day-1/10", border: "border-day-1" },
  { text: "text-day-2", bg: "bg-day-2/10", border: "border-day-2" },
  { text: "text-day-3", bg: "bg-day-3/10", border: "border-day-3" },
  { text: "text-day-4", bg: "bg-day-4/10", border: "border-day-4" },
  { text: "text-day-5", bg: "bg-day-5/10", border: "border-day-5" },
];
