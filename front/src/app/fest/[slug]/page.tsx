import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Building2, CalendarDays, MapPin } from "lucide-react";
import { getColleges, getFestBySlug, getFestEvents } from "@/lib/api";
import { PosterArt } from "@/components/Poster";
import { EntryPassPanel } from "@/components/EntryPassPanel";
import { FestTimeline } from "@/components/FestTimeline";
import { ShareButtons } from "@/components/ShareButtons";
import { FadeUp, Reveal } from "@/components/motion";

type Props = { params: Promise<{ slug: string }> };
export const revalidate = 30;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const f = await getFestBySlug(slug);
  if (!f) return { title: "Fest not found" };
  const description = f.tagline ?? `Events, schedule and registration for ${f.name} on HiveOut.`;
  return { title: f.name, description, openGraph: { title: f.name, description, type: "website" } };
}

const range = (dates: string[]) => {
  if (dates.length === 0) return null;
  const s = [...dates].sort();
  const f = (d: string) => new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  return s[0].slice(0, 10) === s[s.length - 1].slice(0, 10) ? f(s[0]) : `${f(s[0])} to ${f(s[s.length - 1])}`;
};

export default async function FestPage({ params }: Props) {
  const { slug } = await params;
  const [fest, events, colleges] = await Promise.all([getFestBySlug(slug), getFestEvents(slug), getColleges()]);
  if (!fest) notFound();
  const college = colleges?.find((c) => c.id === fest.college_id);
  const dates = range((events ?? []).map((e) => e.date));
  const venues = Array.from(new Set((events ?? []).map((e) => e.location).filter(Boolean) as string[]));

  return (
    <div className="mx-auto max-w-7xl px-5 pb-4 pt-6 sm:px-8">
      <FadeUp>
        <div className="relative h-[22rem] overflow-hidden rounded-[2rem] sm:h-[30rem]">
          <PosterArt id={fest.id} title={fest.name} image={fest.banner_url} kicker="College fest" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/5 to-transparent" />
          <div className="absolute inset-x-3 bottom-3 sm:inset-x-6 sm:bottom-6">
            <div className="glass-photo flex flex-col justify-between gap-5 rounded-[1.5rem] p-5 sm:flex-row sm:items-end sm:p-7">
              <div>
                {college && <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-white/80"><Building2 className="h-4 w-4" />{college.name}</p>}
                <h1 className="font-display text-4xl font-bold leading-[1.02] tracking-tight sm:text-6xl">{fest.name}</h1>
                {fest.tagline && <p className="mt-2 max-w-xl text-white/80">{fest.tagline}</p>}
              </div>
              <div className="flex flex-wrap gap-2 text-sm font-medium text-white/90">
                {dates && <span className="flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1.5"><CalendarDays className="h-4 w-4" />{dates}</span>}
                <span className="rounded-full bg-white/15 px-3 py-1.5">{fest.event_count} event{fest.event_count === 1 ? "" : "s"}</span>
              </div>
            </div>
          </div>
        </div>
      </FadeUp>

      <div className="mt-10 grid gap-10 lg:grid-cols-[1fr_380px]">
        <section aria-labelledby="schedule-h">
          <p className="mb-1.5 text-xs font-bold uppercase tracking-[0.16em] text-amber-ink">Programme</p>
          <h2 id="schedule-h" className="mb-6 font-display text-3xl font-bold tracking-tight sm:text-4xl">The schedule</h2>
          {events === null ? <p className="text-mute">We could not load the schedule right now.</p> : <FestTimeline events={events} />}
        </section>

        <aside className="space-y-5 lg:sticky lg:top-24 lg:self-start">
          <Reveal y={16}><EntryPassPanel slug={fest.slug} name={fest.name} isLive={fest.status === "live"} /></Reveal>
          <div className="rounded-[1.75rem] bg-wash p-6">
            <p className="mb-3 text-sm font-bold">Share this fest</p>
            <ShareButtons title={fest.name} />
            {venues.length > 0 && (
              <div className="mt-6 border-t border-black/5 pt-5">
                <p className="mb-2 text-sm font-bold">Venues</p>
                <ul className="space-y-1.5 text-sm text-mute">{venues.slice(0, 6).map((v) => <li key={v} className="flex items-center gap-2"><MapPin className="h-3.5 w-3.5 shrink-0" />{v}</li>)}</ul>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
