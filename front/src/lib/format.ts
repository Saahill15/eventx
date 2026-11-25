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

/** What to tell the public about registration, from the state the server worked out. Null when it is simply open or not needed. */
export function registrationNote(e: Pick<FestEvent, "registration_state" | "registration_opens_on">): string | null {
  switch (e.registration_state) {
    case "scheduled": return e.registration_opens_on ? `Registration opens on ${formatLongDay(`${e.registration_opens_on}T00:00:00`)}` : "Registration opens soon";
    case "not_open": return "Registration is not open yet";
    case "closed": return "Registration is closed";
    default: return null;
  }
}

/** Short version for a card or timeline badge. Null when registration is open, or not needed. */
export function registrationBadge(e: Pick<FestEvent, "registration_state" | "registration_opens_on">): string | null {
  switch (e.registration_state) {
    case "scheduled": return e.registration_opens_on ? `Opens ${formatMonthDay(e.registration_opens_on)}` : "Opens soon";
    case "not_open": return "Not open yet";
    case "closed": return "Closed";
    default: return null;
  }
}
const formatMonthDay = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short" });

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

/** "2026-12-04" and "2026-12-06" -> 3. Null until both are set and in order. This is only for showing it on the spot: the server works the number out itself. */
export function daysBetween(start?: string | null, end?: string | null): number | null {
  if (!start || !end) return null;
  const n = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 86_400_000) + 1;
  return n >= 1 ? n : null;
}

/** "3 days" or "1 day". */
export const daysLabel = (n: number) => `${n} day${n === 1 ? "" : "s"}`;
