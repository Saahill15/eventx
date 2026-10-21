import Link from "next/link";
import { CalendarDays, MapPin } from "lucide-react";
import type { FestEvent } from "@/lib/types";
import { formatDay, formatTime, priceLabel } from "@/lib/format";
import { EventArt } from "./EventArt";
import { Pill } from "./ui/bits";

export function EventCard({ event }: { event: FestEvent }) {
  return (
    <Link
      href={`/events/${event.id}`}
      className="group glass flex flex-col overflow-hidden rounded-3xl transition duration-300 hover:-translate-y-1 hover:shadow-[var(--shadow-lift)]"
    >
      <div className="relative aspect-[16/10] overflow-hidden">
        <EventArt src={event.image_url} alt={event.title} category={event.category} seed={event.id} className="transition duration-500 group-hover:scale-105" />
        <div className="absolute left-3 top-3 flex gap-2">
          {event.category && <span className="glass-strong rounded-full px-2.5 py-1 text-xs font-semibold">{event.category}</span>}
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-5">
        {event.fest_name && <p className="text-xs font-semibold text-hive-ink">{event.fest_name}</p>}
        <h3 className="font-display text-lg font-bold leading-snug tracking-tight line-clamp-2">{event.title}</h3>
        <div className="mt-auto space-y-1 pt-2 text-sm text-neutral-500">
          <p className="flex items-center gap-2"><CalendarDays className="h-4 w-4 shrink-0" />{formatDay(event.date)}{event.time ? ` · ${formatTime(event.time)}` : ""}</p>
          {event.location && <p className="flex items-center gap-2"><MapPin className="h-4 w-4 shrink-0" /><span className="truncate">{event.location}</span></p>}
        </div>
        <div className="pt-3">
          <Pill tone={event.is_free || !event.price ? "green" : "neutral"}>{priceLabel(event)}</Pill>
        </div>
      </div>
    </Link>
  );
}
