"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { useMemo, useState } from "react";
import { Clock, MapPin } from "lucide-react";
import type { FestEvent } from "@/lib/types";
import { dayKey, formatLongDay, formatTime, priceLabel } from "@/lib/format";
import { EmptyState } from "./ui/bits";

const dayLabel = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });

/** A programme: pick a day, then see each session with its time and place. */
export function Programme({ events, title = "Programme" }: { events: FestEvent[]; title?: string }) {
  const sorted = useMemo(() => [...events].sort((a, b) => a.date.localeCompare(b.date) || (a.time ?? "").localeCompare(b.time ?? "")), [events]);
  const days = useMemo(() => Array.from(new Set(sorted.map((e) => dayKey(e.date)))), [sorted]);
  const [day, setDay] = useState<string | null>(days[0] ?? null);

  if (events.length === 0) return <EmptyState title="No events published yet" body="The committee has not added events. Check back soon." />;
  const shown = sorted.filter((e) => !day || dayKey(e.date) === day);

  return (
    <div className="card p-6 sm:p-10">
      <h2 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h2>
      {day && <p className="mt-2 text-mute">{formatLongDay(day)}</p>}
      <div className="no-scrollbar -mx-6 mt-6 flex gap-2 overflow-x-auto px-6 sm:mx-0 sm:px-0" role="tablist" aria-label="Pick a day">
        {days.map((d, i) => {
          const on = day === d;
          return (
            <button key={d} role="tab" aria-selected={on} onClick={() => setDay(d)} className="relative shrink-0 rounded-2xl px-5 py-3 text-sm font-semibold transition-colors">
              {on ? <motion.span layoutId={`prog-${title}`} className="absolute inset-0 rounded-2xl bg-brand shadow-[var(--shadow-glow)]" transition={{ type: "spring", stiffness: 420, damping: 34 }} /> : <span className="absolute inset-0 rounded-2xl bg-chip" />}
              <span className={`relative ${on ? "text-white" : "text-chip-ink"}`}>Day {i + 1} <span className="font-normal opacity-80">· {dayLabel(d)}</span></span>
            </button>
          );
        })}
      </div>

      <ul className="mt-6 space-y-4">
        {shown.map((e, i) => (
          <motion.li key={e.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05, duration: 0.4 }}>
            <Link href={`/events/${e.id}`} className="group flex flex-col gap-4 rounded-3xl bg-wash p-5 transition hover:bg-chip sm:flex-row sm:items-center sm:justify-between sm:p-6">
              <div className="min-w-0">
                {e.fest_name && <p className="mb-1 text-sm font-medium text-chip-ink">{e.fest_name}</p>}
                <h3 className="font-display text-xl font-semibold leading-snug tracking-tight sm:text-2xl">{e.title}</h3>
                {e.description && <p className="mt-2 line-clamp-2 max-w-2xl text-mute">{e.description}</p>}
              </div>
              <div className="flex shrink-0 flex-wrap gap-2 sm:max-w-[14rem] sm:justify-end">
                {e.time && <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3.5 py-1.5 text-sm font-medium text-chip-ink shadow-[var(--shadow-card)]"><Clock className="h-3.5 w-3.5" />{formatTime(e.time)}</span>}
                {e.location && <span className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-white px-3.5 py-1.5 text-sm font-medium text-chip-ink shadow-[var(--shadow-card)]"><MapPin className="h-3.5 w-3.5 shrink-0" /><span className="truncate">{e.location}</span></span>}
                <span className={`inline-flex items-center rounded-full px-3.5 py-1.5 text-sm font-semibold ${e.is_free || !e.price ? "bg-mint text-emerald-800" : "bg-chip text-chip-ink"}`}>{e.requires_registration && (e.is_free || !e.price) ? "Register free" : priceLabel(e)}</span>
              </div>
            </Link>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}
