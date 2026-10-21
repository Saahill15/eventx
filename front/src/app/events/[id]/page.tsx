import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CalendarDays, Clock, MapPin, Tag } from "lucide-react";
import { getEventById, getFestEvents } from "@/lib/api";
import { formatLongDay, formatTime, mapsLink, priceLabel, startOfToday } from "@/lib/format";
import { EventArt } from "@/components/EventArt";
import { EventCard } from "@/components/EventCard";
import { RegisterPanel } from "@/components/RegisterPanel";
import { ShareButtons } from "@/components/ShareButtons";
import { Pill } from "@/components/ui/bits";

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

  const more = event.fest_slug ? ((await getFestEvents(event.fest_slug)) ?? []).filter((e) => e.id !== event.id).slice(0, 3) : [];
  const hasEnded = new Date(event.date) < startOfToday();

  return (
    <div className="mx-auto max-w-6xl px-6 pb-8 pt-4">
      <nav className="mb-5 text-sm text-neutral-500" aria-label="Breadcrumb">
        <Link href="/events" className="hover:text-ink">Events</Link>
        {event.fest_slug && <> <span aria-hidden>/</span> <Link href={`/fest/${event.fest_slug}`} className="hover:text-ink">{event.fest_name}</Link></>}
      </nav>

      <div className="grid gap-8 lg:grid-cols-[1fr_380px]">
        <div>
          <div className="glass aspect-[16/9] overflow-hidden rounded-[2rem] p-1.5">
            <div className="h-full w-full overflow-hidden rounded-[1.6rem]">
              <EventArt src={event.image_url} alt={event.title} category={event.category} seed={event.id} />
            </div>
          </div>

          <div className="mt-8 flex flex-wrap items-center gap-2">
            {event.category && <Pill tone="amber">{event.category}</Pill>}
            <Pill tone={event.is_free || !event.price ? "green" : "neutral"}>{priceLabel(event)}</Pill>
            {event.requires_registration && <Pill>Registration required</Pill>}
          </div>
          <h1 className="mt-4 font-display text-4xl font-black leading-[1.05] tracking-tight sm:text-5xl">{event.title}</h1>
          {event.fest_slug && (
            <p className="mt-3 text-neutral-500">Part of <Link href={`/fest/${event.fest_slug}`} className="font-semibold text-ink hover:underline">{event.fest_name}</Link>{event.college_name ? ` · ${event.college_name}` : ""}</p>
          )}

          {event.description && (
            <section className="mt-10">
              <h2 className="font-display text-xl font-extrabold tracking-tight">About this event</h2>
              <p className="mt-3 max-w-2xl whitespace-pre-line leading-relaxed text-neutral-600">{event.description}</p>
            </section>
          )}
        </div>

        <aside className="lg:sticky lg:top-28 lg:self-start">
          <div className="glass-strong space-y-5 rounded-[2rem] p-6">
            <dl className="space-y-4 text-[0.9375rem]">
              <Row icon={<CalendarDays className="h-5 w-5" />} label="Date">{formatLongDay(event.date)}</Row>
              {event.time && <Row icon={<Clock className="h-5 w-5" />} label="Time">{formatTime(event.time)}</Row>}
              {event.location && (
                <Row icon={<MapPin className="h-5 w-5" />} label="Venue">
                  {event.location}
                  <a href={mapsLink(event.location, event.college_name)} target="_blank" rel="noopener noreferrer" className="ml-2 text-sm font-semibold text-hive-ink hover:underline">Map</a>
                </Row>
              )}
              <Row icon={<Tag className="h-5 w-5" />} label="Price">{priceLabel(event)}</Row>
            </dl>
            <RegisterPanel event={event} hasEnded={hasEnded} />
            <div className="border-t border-black/5 pt-5">
              <ShareButtons title={event.title} calendar={{ title: event.title, date: event.date, time: event.time, location: event.location, description: event.description }} />
            </div>
          </div>
        </aside>
      </div>

      {more.length > 0 && (
        <section className="mt-16">
          <h2 className="mb-5 font-display text-2xl font-extrabold tracking-tight">More from {event.fest_name}</h2>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{more.map((e) => <EventCard key={e.id} event={e} />)}</div>
        </section>
      )}
    </div>
  );
}

function Row({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 text-neutral-400">{icon}</span>
      <div><dt className="text-xs font-semibold uppercase tracking-wide text-neutral-400">{label}</dt><dd className="font-medium">{children}</dd></div>
    </div>
  );
}
