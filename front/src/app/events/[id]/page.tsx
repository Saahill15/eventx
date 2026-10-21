import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CalendarDays, Clock, MapPin, Tag } from "lucide-react";
import { getEventById, getFestEvents } from "@/lib/api";
import { formatLongDay, formatTime, mapsLink, priceLabel, startOfToday } from "@/lib/format";
import { PosterArt, PosterCard } from "@/components/Poster";
import { RegisterPanel } from "@/components/RegisterPanel";
import { Rail, RailItem } from "@/components/Rail";
import { ShareButtons } from "@/components/ShareButtons";
import { TicketShell } from "@/components/TicketShell";
import { FadeUp } from "@/components/motion";
import { Pill, SectionHead } from "@/components/ui/bits";

type Props = { params: Promise<{ id: string }> };
export const revalidate = 30;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const e = await getEventById(id);
  if (!e) return { title: "Event not found" };
  const when = `${formatLongDay(e.date)}${e.time ? `, ${formatTime(e.time)}` : ""}`;
  const description = [when, e.location, e.fest_name].filter(Boolean).join(" · ");
  return { title: e.title, description, openGraph: { title: e.title, description, type: "website" } };
}

export default async function EventPage({ params }: Props) {
  const { id } = await params;
  const event = await getEventById(id);
  if (!event) notFound();

  const more = event.fest_slug ? ((await getFestEvents(event.fest_slug)) ?? []).filter((e) => e.id !== event.id) : [];
  const hasEnded = new Date(event.date) < startOfToday();
  const facts = [
    { icon: CalendarDays, label: "Date", value: formatLongDay(event.date) },
    ...(event.time ? [{ icon: Clock, label: "Time", value: formatTime(event.time) }] : []),
    ...(event.location ? [{ icon: MapPin, label: "Venue", value: event.location }] : []),
    { icon: Tag, label: "Price", value: priceLabel(event) },
  ];

  return (
    <div className="mx-auto max-w-7xl px-5 pb-4 pt-6 sm:px-8">
      <nav className="mb-6 text-sm text-mute" aria-label="Breadcrumb">
        <Link href="/events" className="hover:text-ink">Events</Link>
        {event.fest_slug && <> <span aria-hidden>/</span> <Link href={`/fest/${event.fest_slug}`} className="hover:text-ink">{event.fest_name}</Link></>}
      </nav>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_400px]">
        <FadeUp>
          <div className="grid gap-8 md:grid-cols-[300px_1fr]">
            <div className="mx-auto w-full max-w-xs md:max-w-none">
              <div className="aspect-[3/4] overflow-hidden rounded-[var(--radius-poster)] shadow-[var(--shadow-pop)]"><PosterArt id={event.id} title={event.title} image={event.image_url} kicker={event.fest_name ?? event.category} /></div>
            </div>
            <div>
              <div className="mb-4 flex flex-wrap gap-2">
                {event.category && <Pill tone="amber">{event.category}</Pill>}
                <Pill tone={event.is_free || !event.price ? "green" : "neutral"}>{priceLabel(event)}</Pill>
                {event.requires_registration && <Pill tone="lilac">Registration required</Pill>}
              </div>
              <h1 className="font-display text-4xl font-bold leading-[1.02] tracking-[-0.02em] sm:text-6xl">{event.title}</h1>
              {event.fest_slug && <p className="mt-4 text-mute">Part of <Link href={`/fest/${event.fest_slug}`} className="font-semibold text-ink underline underline-offset-4">{event.fest_name}</Link>{event.college_name ? ` · ${event.college_name}` : ""}</p>}
              <dl className="mt-8 grid gap-3 sm:grid-cols-2">
                {facts.map(({ icon: Icon, label, value }) => (
                  <div key={label} className="flex items-start gap-3 rounded-2xl bg-wash p-4">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white"><Icon className="h-4 w-4" /></span>
                    <div className="min-w-0"><dt className="text-[11px] font-bold uppercase tracking-wider text-mute">{label}</dt><dd className="font-semibold leading-snug">{value}{label === "Venue" && event.location && <a href={mapsLink(event.location, event.college_name)} target="_blank" rel="noopener noreferrer" className="ml-2 text-sm text-amber-ink underline underline-offset-2">Map</a>}</dd></div>
                  </div>
                ))}
              </dl>
              {event.description && <section className="mt-8"><h2 className="font-display text-2xl font-bold tracking-tight">About this event</h2><p className="mt-3 max-w-2xl whitespace-pre-line leading-relaxed text-neutral-600">{event.description}</p></section>}
            </div>
          </div>
        </FadeUp>

        <aside className="lg:sticky lg:top-24 lg:self-start">
          <TicketShell
            tint="bg-butter"
            head={<div><p className="text-[11px] font-bold uppercase tracking-[0.18em] text-amber-ink">Your ticket</p><p className="mt-1 line-clamp-2 font-display text-2xl font-bold leading-tight tracking-tight">{event.title}</p><p className="mt-1 text-sm text-amber-ink">{formatLongDay(event.date)}{event.time ? ` · ${formatTime(event.time)}` : ""}</p></div>}
          >
            <RegisterPanel event={event} hasEnded={hasEnded} />
            <div className="mt-6 border-t border-black/5 pt-5">
              <ShareButtons title={event.title} calendar={{ title: event.title, date: event.date, time: event.time, location: event.location, description: event.description }} />
            </div>
          </TicketShell>
        </aside>
      </div>

      {more.length > 0 && (
        <section className="pt-16">
          <SectionHead kicker="Same fest" title={`More from ${event.fest_name}`} />
          <Rail label="More from this fest">{more.slice(0, 10).map((e) => <RailItem key={e.id}><PosterCard event={e} /></RailItem>)}</Rail>
        </section>
      )}
    </div>
  );
}
