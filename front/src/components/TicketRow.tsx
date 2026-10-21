"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { ArrowUpRight, Clock, MapPin } from "lucide-react";
import type { FestEvent } from "@/lib/types";
import { formatDayNumber, formatMonthShort, formatTime, priceLabel } from "@/lib/format";

/** One event as a session card: date tile, title, and chips for time, place and price. */
export function TicketRow({ event }: { event: FestEvent }) {
  const free = event.is_free || !event.price;
  return (
    <motion.div whileHover={{ y: -3 }} transition={{ type: "spring", stiffness: 300, damping: 24 }}>
      <Link href={`/events/${event.id}`} className="group card flex items-center gap-4 p-4 transition hover:shadow-[var(--shadow-pop)] sm:gap-6 sm:p-5">
        <div className="flex h-20 w-20 shrink-0 flex-col items-center justify-center rounded-2xl bg-chip text-chip-ink sm:h-24 sm:w-24">
          <span className="font-display text-3xl font-semibold leading-none sm:text-4xl">{formatDayNumber(event.date)}</span>
          <span className="mt-1 text-xs font-semibold tracking-widest opacity-80">{formatMonthShort(event.date)}</span>
        </div>
        <div className="min-w-0 flex-1">
          {event.fest_name && <p className="mb-0.5 truncate text-sm font-medium text-chip-ink">{event.fest_name}</p>}
          <h3 className="truncate font-display text-xl font-semibold tracking-tight sm:text-2xl">{event.title}</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {event.time && <span className="inline-flex items-center gap-1.5 rounded-full bg-wash px-3 py-1 text-xs font-medium text-mute"><Clock className="h-3 w-3" />{formatTime(event.time)}</span>}
            {event.location && <span className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-wash px-3 py-1 text-xs font-medium text-mute"><MapPin className="h-3 w-3 shrink-0" /><span className="truncate">{event.location}</span></span>}
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${free ? "bg-mint text-emerald-800" : "bg-chip text-chip-ink"}`}>{priceLabel(event)}</span>
          </div>
        </div>
        <ArrowUpRight className="hidden h-5 w-5 shrink-0 text-neutral-300 transition group-hover:text-chip-ink sm:block" />
      </Link>
    </motion.div>
  );
}
