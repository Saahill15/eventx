"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { ArrowUpRight, MapPin } from "lucide-react";
import type { FestEvent } from "@/lib/types";
import { formatDayNumber, formatMonthShort, formatTime, priceLabel } from "@/lib/format";
import { tintFor } from "./Poster";

/** A horizontal ticket-stub row: date tear-off on the left, details in the middle, price on the right. */
export function TicketRow({ event }: { event: FestEvent }) {
  const t = tintFor(event.id);
  return (
    <motion.div whileHover={{ x: 4 }} transition={{ type: "spring", stiffness: 300, damping: 24 }}>
      <Link href={`/events/${event.id}`} className="group relative flex items-stretch overflow-hidden rounded-3xl bg-white shadow-[var(--shadow-soft)] ring-1 ring-black/5 transition hover:shadow-[var(--shadow-pop)]">
        <div className="flex w-20 shrink-0 flex-col items-center justify-center px-2 py-5 sm:w-28" style={{ background: t.bg, color: t.ink }}>
          <span className="font-display text-4xl font-bold leading-none sm:text-5xl">{formatDayNumber(event.date)}</span>
          <span className="mt-1 text-xs font-bold tracking-widest opacity-70">{formatMonthShort(event.date)}</span>
        </div>
        {/* perforation */}
        <div className="relative w-0 border-l-2 border-dashed border-black/10">
          <span className="absolute -left-[9px] -top-[9px] h-[18px] w-[18px] rounded-full bg-wash ring-1 ring-black/5" />
          <span className="absolute -bottom-[9px] -left-[9px] h-[18px] w-[18px] rounded-full bg-wash ring-1 ring-black/5" />
        </div>
        <div className="flex min-w-0 flex-1 items-center justify-between gap-4 px-5 py-4 sm:px-6">
          <div className="min-w-0">
            {event.fest_name && <p className="mb-0.5 truncate text-xs font-bold uppercase tracking-wider text-amber-ink">{event.fest_name}</p>}
            <h3 className="truncate font-display text-xl font-semibold tracking-tight sm:text-2xl">{event.title}</h3>
            <p className="mt-1 flex items-center gap-1.5 truncate text-sm text-mute"><MapPin className="h-3.5 w-3.5 shrink-0" />{event.location ?? "Venue to be announced"}{event.time ? ` · ${formatTime(event.time)}` : ""}</p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-2">
            <span className={`rounded-full px-3 py-1 text-xs font-bold ${event.is_free || !event.price ? "bg-mint text-emerald-800" : "bg-wash"}`}>{priceLabel(event)}</span>
            <ArrowUpRight className="h-5 w-5 text-neutral-300 transition group-hover:text-ink" />
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
