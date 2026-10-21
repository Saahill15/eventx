import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CalendarDays, Clock, MapPin, Tag } from "lucide-react";
import { getEventById, getFestEvents } from "@/lib/api";
import { formatLongDay, formatTime, mapsLink, priceLabel, startOfToday } from "@/lib/format";
import { PosterArt } from "@/components/Poster";
import { RegisterPanel } from "@/components/RegisterPanel";
import { ShareButtons } from "@/components/ShareButtons";
import { Programme } from "@/components/Programme";
import { TicketShell } from "@/components/TicketShell";
import { FadeUp, Reveal } from "@/components/motion";
import { InfoChip } from "@/components/ui/bits";

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
    <>
      <section className="dots relative overflow-hidden px-4 pb-12 pt-10 text-center sm:pt-16">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-80 bg-gradient-to-b from-white/70 to-transparent" aria-hidden />
        <div className="relative mx-auto max-w-4xl">
          <FadeUp className="flex flex-wrap justify-center gap-2.5">
            <InfoChip icon={<CalendarDays className="h-4 w-4" />}>{formatLongDay(event.date)}</InfoChip>
            {event.location && <InfoChip icon={<MapPin className="h-4 w-4" />}>{event.location}</InfoChip>}
          </FadeUp>
          <FadeUp delay={0.08}><h1 className="mt-7 font-display text-5xl font-semibold leading-[1.02] tracking-[-0.03em] sm:text-7xl">{event.title}</h1></FadeUp>
          {event.fest_slug && <FadeUp delay={0.14}><p className="mt-5 text-lg text-mute">Part of <Link href={`/fest/${event.fest_slug}`} className="font-semibold text-chip-ink hover:underline">{event.fest_name}</Link>{event.college_name ? ` · ${event.college_name}` : ""}</p></FadeUp>}
          <FadeUp delay={0.2} className="mt-8 flex justify-center"><ShareButtons title={event.title} calendar={{ title: event.title, date: event.date, time: event.time, location: event.location, description: event.description }} /></FadeUp>
        </div>
      </section>

      <div className="mx-auto max-w-7xl space-y-5 px-4 sm:px-6">
        <div className="grid gap-5 lg:grid-cols-[1fr_420px]">
          <div className="space-y-5">
            <Reveal><div className="card overflow-hidden p-3 sm:p-4"><div className="aspect-[16/10] overflow-hidden rounded-[1.25rem]"><PosterArt id={event.id} title={event.title} image={event.image_url} kicker={event.fest_name ?? event.category} /></div></div></Reveal>
            <Reveal>
              <div className="card p-6 sm:p-10">
                <h2 className="font-display text-3xl font-semibold tracking-tight">About this event</h2>
                {event.description ? <p className="mt-4 max-w-2xl whitespace-pre-line text-lg leading-relaxed text-mute">{event.description}</p> : <p className="mt-4 text-mute">The organisers have not added a description yet.</p>}
                <dl className="mt-8 grid gap-3 sm:grid-cols-2">
                  {facts.map(({ icon: Icon, label, value }) => (
                    <div key={label} className="flex items-start gap-3 rounded-2xl bg-wash p-4">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-chip text-chip-ink"><Icon className="h-4 w-4" /></span>
                      <div className="min-w-0"><dt className="text-xs font-medium text-mute">{label}</dt><dd className="font-semibold leading-snug">{value}{label === "Venue" && event.location && <a href={mapsLink(event.location, event.college_name)} target="_blank" rel="noopener noreferrer" className="ml-2 text-sm font-medium text-chip-ink underline underline-offset-2">Map</a>}</dd></div>
                    </div>
                  ))}
                </dl>
              </div>
            </Reveal>
          </div>

          <aside className="lg:sticky lg:top-24 lg:self-start">
            <Reveal>
              <TicketShell head={<div><p className="text-sm font-semibold text-chip-ink">Your ticket</p><p className="mt-1 line-clamp-2 font-display text-2xl font-semibold leading-tight tracking-tight">{event.title}</p><p className="mt-1 text-sm text-chip-ink/80">{formatLongDay(event.date)}{event.time ? ` · ${formatTime(event.time)}` : ""}</p></div>}>
                <RegisterPanel event={event} hasEnded={hasEnded} />
              </TicketShell>
            </Reveal>
          </aside>
        </div>

        {more.length > 0 && <Reveal><Programme events={more} title={`More from ${event.fest_name}`} /></Reveal>}
      </div>
    </>
  );
}
