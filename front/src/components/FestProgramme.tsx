"use client";

import { useMemo, useState } from "react";
import type { FestEvent } from "@/lib/types";
import { dayKey, formatLongDay, formatTime } from "@/lib/format";
import { ProgrammeCard } from "./Programme";
import { EmptyState } from "./ui/bits";

const pad = (n: number) => String(n).padStart(2, "0");
const addDays = (iso: string, n: number) => {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};
const short = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });

/** Which part of the day a start time falls in. Events with no time yet are listed last. */
const PART = ["Morning", "Afternoon", "Evening", "Time to be announced"] as const;
const partOf = (time: string | null): (typeof PART)[number] => {
  if (!time) return "Time to be announced";
  const h = Number(time.split(":")[0]);
  return h < 12 ? "Morning" : h < 17 ? "Afternoon" : "Evening";
};

interface Placed { event: FestEvent; day: number; of: number } // which day of the event this is, and how many days it runs

/**
 * A fest's programme, day by day. Every day of the fest gets its own section (even an empty one), numbered from the fest's first day.
 * An event that runs for several days appears on each of them, marked "Day 2 of 3". Within a day, events are grouped morning,
 * afternoon and evening. "All days" shows the whole fest in order; picking a day shows just that one.
 */
export function FestProgramme({ events, startDate, daysCount, title = "Programme" }: { events: FestEvent[]; startDate?: string | null; daysCount?: number | null; title?: string }) {
  const { days, byDay } = useMemo(() => {
    const placed = new Map<string, Placed[]>();
    for (const e of events) {
      const first = dayKey(e.date);
      const span = Math.max(1, e.span_days ?? 1);
      for (let i = 0; i < span; i++) {
        const k = addDays(first, i);
        placed.set(k, [...(placed.get(k) ?? []), { event: e, day: i + 1, of: span }]);
      }
    }
    // The fest's own days when it has them; otherwise just the days that have events
    const keys = new Set(placed.keys());
    if (startDate && daysCount && daysCount > 0) for (let i = 0; i < daysCount; i++) keys.add(addDays(startDate.slice(0, 10), i));
    const days = Array.from(keys).sort();
    for (const list of placed.values()) list.sort((a, b) => (a.event.time ?? "99:99").localeCompare(b.event.time ?? "99:99") || a.event.title.localeCompare(b.event.title));
    return { days, byDay: placed };
  }, [events, startDate, daysCount]);

  const [pick, setPick] = useState<string | "all">("all");
  if (events.length === 0) return <EmptyState title="No events published yet" body="The committee has not added events. Check back soon." />;

  const number = (iso: string) => days.indexOf(iso) + 1;
  const shown = pick === "all" ? days : days.filter((d) => d === pick);

  return (
    <section className="card p-6 sm:p-10" aria-label={title}>
      <h2 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h2>
      <p className="mt-2 text-mute">{days.length > 1 ? `${days.length} days, ${events.length} event${events.length === 1 ? "" : "s"}. ` : ""}Pick a day, or read it all.</p>

      {days.length > 1 && (
        <div className="no-scrollbar -mx-6 mt-6 flex gap-2 overflow-x-auto px-6 sm:mx-0 sm:px-0" role="group" aria-label="Pick a day">
          {(["all", ...days] as const).map((d) => {
            const on = pick === d;
            return (
              <button key={d} onClick={() => setPick(d)} aria-pressed={on} className={`shrink-0 rounded-2xl px-5 py-3 text-sm font-semibold transition ${on ? "bg-ink text-white" : "bg-chip text-chip-ink hover:bg-tint"}`}>
                {d === "all" ? "All days" : <>Day {number(d)} <span className="font-normal opacity-80">· {short(d)}</span></>}
              </button>
            );
          })}
        </div>
      )}

      <div className="mt-8 space-y-12">
        {shown.map((d) => {
          const list = byDay.get(d) ?? [];
          const venues = new Set(list.map((p) => p.event.location).filter(Boolean));
          return (
            <section key={d} aria-label={`Day ${number(d)}`}>
              <div className="mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-1 border-b border-black/10 pb-3">
                <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-chip-ink">Day {number(d)}</p><h3 className="font-display text-2xl font-semibold tracking-tight">{formatLongDay(`${d}T00:00:00`)}</h3></div>
                <p className="text-sm text-mute">{list.length === 0 ? "Nothing scheduled yet" : `${list.length} event${list.length === 1 ? "" : "s"}${venues.size > 0 ? ` · ${venues.size} venue${venues.size === 1 ? "" : "s"}` : ""}${list.some((p) => p.event.time) ? ` · from ${formatTime(list.find((p) => p.event.time)!.event.time)}` : ""}`}</p>
              </div>
              {list.length === 0 ? <p className="rounded-2xl bg-wash px-5 py-6 text-center text-mute">Nothing is scheduled for this day yet. Check back soon.</p> : (
                <div className="space-y-7">
                  {PART.map((part) => {
                    const rows = list.filter((p) => partOf(p.event.time) === part);
                    if (rows.length === 0) return null;
                    return (
                      <div key={part}>
                        {list.some((p) => partOf(p.event.time) !== part) && <p className="mb-3 text-sm font-semibold text-mute">{part}</p>}
                        <ul className="space-y-4">
                          {rows.map((p) => (
                            <li key={`${p.event.id}-${d}`}><ProgrammeCard e={p.event} note={p.of > 1 ? `Day ${p.day} of ${p.of}${p.day < p.of ? ` · continues until ${short(addDays(dayKey(p.event.date), p.of - 1))}` : " · last day"}` : undefined} /></li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          );
        })}
      </div>
    </section>
  );
}
