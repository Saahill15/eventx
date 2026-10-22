"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { MapPin } from "lucide-react";
import { mediaSrc } from "@/lib/api";
import type { FestEvent } from "@/lib/types";
import { formatDayNumber, formatMonthShort, formatTime, priceLabel } from "@/lib/format";

const TINTS = [
  { bg: "linear-gradient(160deg,#35353b,#111111)", ink: "#ffffff" },
  { bg: "linear-gradient(160deg,#3b3220,#111111)", ink: "#ffffff" },
  { bg: "linear-gradient(160deg,#25303d,#111111)", ink: "#ffffff" },
  { bg: "linear-gradient(160deg,#3a2a2a,#111111)", ink: "#ffffff" },
  { bg: "linear-gradient(160deg,#2c3a30,#111111)", ink: "#ffffff" },
];

export const tintFor = (id: number) => TINTS[id % TINTS.length];

/** Cover art: the photo when there is one, otherwise a typographic poster so every listing looks designed. */
export function PosterArt({ id, title, image, kicker, className = "", showTitle = true }: { id: number; title: string; image?: string | null; kicker?: string | null; className?: string; showTitle?: boolean }) {
  if (image) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={mediaSrc(image) ?? image} alt={title} loading="lazy" referrerPolicy="no-referrer" className={`h-full w-full object-cover ${className}`} />;
  }
  const t = tintFor(id);
  return (
    <div className={`relative h-full w-full overflow-hidden ${className}`} style={{ background: t.bg, color: t.ink }} role="img" aria-label={title}>
      <svg className="absolute -right-8 -top-10 h-56 w-56 opacity-25" viewBox="0 0 100 115" aria-hidden><path d="M50 4 94 29v57L50 111 6 86V29z" fill="none" stroke="currentColor" strokeWidth="3" /><path d="M50 24 76 39v37L50 91 24 76V39z" fill="none" stroke="currentColor" strokeWidth="3" /></svg>
      <div className="absolute inset-x-5 top-5">{kicker && <span className="text-[11px] font-bold uppercase tracking-[0.16em] opacity-70">{kicker}</span>}</div>
      {showTitle && <p className="absolute inset-x-5 bottom-24 font-display text-[1.7rem] font-semibold leading-[1.02] tracking-tight line-clamp-4 sm:text-3xl">{title}</p>}
    </div>
  );
}

/** Portrait poster for an event, used in rails and grids. */
export function PosterCard({ event, className = "" }: { event: FestEvent; className?: string }) {
  return (
    <motion.div whileHover={{ y: -6 }} transition={{ type: "spring", stiffness: 300, damping: 22 }} className={className}>
      <Link href={`/events/${event.id}`} className="group relative block aspect-[3/4] overflow-hidden rounded-3xl bg-wash shadow-[var(--shadow-card)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
        <div className="h-full w-full transition duration-700 group-hover:scale-105">
          <PosterArt id={event.id} title={event.title} image={event.image_url} kicker={event.fest_name ?? event.category} showTitle={false} />
        </div>
        <div className="absolute left-3 top-3 flex h-14 w-12 flex-col items-center justify-center rounded-2xl bg-white text-ink shadow-md">
          <span className="font-display text-xl font-bold leading-none">{formatDayNumber(event.date)}</span>
          <span className="mt-0.5 text-[10px] font-bold tracking-wider text-mute">{formatMonthShort(event.date)}</span>
        </div>
        <span className={`absolute right-3 top-3 rounded-full px-2.5 py-1 text-xs font-bold ${event.is_free || !event.price ? "bg-mint text-emerald-800" : "bg-white text-ink"}`}>{priceLabel(event)}</span>
        <div className="glass-photo absolute inset-x-2.5 bottom-2.5 rounded-[1.25rem] p-3.5">
          <p className="line-clamp-2 font-display text-lg font-semibold leading-tight tracking-tight">{event.title}</p>
          <p className="mt-1 flex items-center gap-1.5 text-xs text-white/80"><MapPin className="h-3.5 w-3.5 shrink-0" /><span className="truncate">{event.location ?? "Venue to be announced"}{event.time ? ` · ${formatTime(event.time)}` : ""}</span></p>
        </div>
      </Link>
    </motion.div>
  );
}
