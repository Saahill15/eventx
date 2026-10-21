import type { FestEvent } from "./types";

// Dates arrive as local wall-clock times without a timezone, so they are formatted as written.
const parse = (iso: string) => new Date(iso);

export const formatDay = (iso: string) =>
  parse(iso).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });

export const formatLongDay = (iso: string) =>
  parse(iso).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

export const formatMonthShort = (iso: string) => parse(iso).toLocaleDateString("en-IN", { month: "short" }).toUpperCase();
export const formatDayNumber = (iso: string) => parse(iso).getDate();

/** "10:00" -> "10:00 am" */
export function formatTime(time: string | null): string {
  if (!time) return "";
  const [h, m] = time.split(":").map(Number);
  if (Number.isNaN(h)) return time;
  const suffix = h >= 12 ? "pm" : "am";
  return `${((h + 11) % 12) + 1}:${String(m ?? 0).padStart(2, "0")} ${suffix}`;
}

export const priceLabel = (e: Pick<FestEvent, "is_free" | "price">) =>
  e.is_free || !e.price ? "Free" : `₹${Number(e.price).toLocaleString("en-IN")}`;

/** Calendar-day key used to group events by day */
export const dayKey = (iso: string) => iso.slice(0, 10);

export function startOfToday(): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

export const isUpcoming = (e: Pick<FestEvent, "date">) => parse(e.date) >= startOfToday();

export function isThisWeek(e: Pick<FestEvent, "date">): boolean {
  const start = startOfToday();
  const end = new Date(start);
  end.setDate(end.getDate() + 7);
  const d = parse(e.date);
  return d >= start && d < end;
}

export function mapsLink(venue: string, area?: string | null): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent([venue, area].filter(Boolean).join(", "))}`;
}
