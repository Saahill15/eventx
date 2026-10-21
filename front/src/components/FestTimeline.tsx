"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { useMemo, useState } from "react";
import { MapPin } from "lucide-react";
import type { FestEvent } from "@/lib/types";
import { dayKey, formatDayNumber, formatLongDay, formatMonthShort, formatTime, priceLabel } from "@/lib/format";
import { tintFor } from "./Poster";
import { Chip } from "./ui/Chip";
import { EmptyState } from "./ui/bits";

/** The fest programme as a timeline: pick a day, then see each event in time order. */
export function FestTimeline({ events }: { events: FestEvent[] }) {
  const sorted = useMemo(() => [...events].sort((a, b) => a.date.localeCompare(b.date) || (a.time ?? "").localeCompare(b.time ?? "")), [events]);
  const days = useMemo(() => Array.from(new Set(sorted.map((e) => dayKey(e.date)))), [sorted]);
  const categories = useMemo(() => Array.from(new Set(sorted.map((e) => e.category).filter(Boolean) as string[])).sort(), [sorted]);
  const [day, setDay] = useState<string | null>(days[0] ?? null);
  const [category, setCategory] = useState<string | null>(null);

  if (events.length === 0) return <EmptyState title="No events published yet" body="The committee has not added events. Check back soon." />;

  const shown = sorted.filter((e) => (!day || dayKey(e.date) === day) && (!category || e.category === category));

  return (
    <div>
      <div className="no-scrollbar -mx-5 flex gap-2 overflow-x-auto px-5 pb-1 sm:mx-0 sm:px-0" role="group" aria-label="Pick a day">
        {days.map((d) => {
          const on = day === d;
          return (
            <button key={d} onClick={() => setDay(d)} aria-pressed={on} className="relative flex h-20 w-[4.5rem] shrink-0 flex-col items-center justify-center rounded-2xl bg-wash transition hover:bg-neutral-200">
              {on && <motion.span layoutId="timeline-day" className="absolute inset-0 rounded-2xl bg-ink" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
              <span className={`relative font-display text-2xl font-bold leading-none ${on ? "text-white" : ""}`}>{formatDayNumber(d)}</span>
              <span className={`relative mt-1 text-[11px] font-bold tracking-wider ${on ? "text-white/70" : "text-mute"}`}>{formatMonthShort(d)}</span>
            </button>
          );
        })}
      </div>
      {categories.length > 1 && (
        <div className="no-scrollbar -mx-5 mt-3 flex gap-2 overflow-x-auto px-5 sm:mx-0 sm:px-0">
          {categories.map((c) => <Chip key={c} active={category === c} onClick={() => setCategory(category === c ? null : c)}>{c}</Chip>)}
        </div>
      )}
      {day && <p className="mb-6 mt-6 font-display text-xl font-bold tracking-tight">{formatLongDay(day)}</p>}

      {shown.length === 0 ? <EmptyState title="Nothing on this day" body="Try another day or category." /> : (
        <ol className="relative space-y-4 border-l-2 border-black/10 pl-6 sm:pl-8">
          {shown.map((e, i) => {
            const t = tintFor(e.id);
            return (
              <motion.li key={e.id} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05, duration: 0.4 }} className="relative">
                <span className="absolute -left-[2.15rem] top-6 h-4 w-4 rounded-full border-4 border-white sm:-left-[2.65rem]" style={{ background: t.ink }} />
                <p className="mb-1.5 text-sm font-bold tabular-nums text-mute">{e.time ? formatTime(e.time) : "Time to be announced"}</p>
                <Link href={`/events/${e.id}`} className="group flex items-center justify-between gap-4 rounded-3xl p-5 transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-card)]" style={{ background: t.bg }}>
                  <div className="min-w-0" style={{ color: t.ink }}>
                    {e.category && <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.16em] opacity-70">{e.category}</p>}
                    <h3 className="font-display text-xl font-bold leading-tight tracking-tight">{e.title}</h3>
                    {e.location && <p className="mt-1 flex items-center gap-1.5 text-sm opacity-75"><MapPin className="h-3.5 w-3.5" />{e.location}</p>}
                  </div>
                  <span className="shrink-0 rounded-full bg-white/80 px-3 py-1 text-xs font-bold">{e.requires_registration ? "Register" : priceLabel(e)}</span>
                </Link>
              </motion.li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
