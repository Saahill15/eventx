import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Building2, CalendarDays, MapPin, Ticket } from "lucide-react";
import { getColleges, getFestBySlug, getFestEvents } from "@/lib/api";
import { PosterArt } from "@/components/Poster";
import { EntryPassPanel } from "@/components/EntryPassPanel";
import { Programme } from "@/components/Programme";
import { ShareButtons } from "@/components/ShareButtons";
import { FadeUp, Reveal } from "@/components/motion";
import { InfoChip } from "@/components/ui/bits";

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
  const f = (d: string) => new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "long" });
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
    <>
      <section className="dots relative overflow-hidden px-4 pb-14 pt-10 text-center sm:pt-16">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-80 bg-gradient-to-b from-white/70 to-transparent" aria-hidden />
        <div className="relative mx-auto max-w-4xl">
          <FadeUp className="flex flex-wrap justify-center gap-2.5">
            {dates && <InfoChip icon={<CalendarDays className="h-4 w-4" />}>{dates}</InfoChip>}
            {college && <InfoChip icon={<Building2 className="h-4 w-4" />}>{college.name}</InfoChip>}
          </FadeUp>
          <FadeUp delay={0.08}><h1 className="mt-7 font-display text-5xl font-semibold leading-[1.02] tracking-[-0.03em] sm:text-7xl lg:text-8xl">{fest.name}</h1></FadeUp>
          {fest.tagline && <FadeUp delay={0.14}><p className="mx-auto mt-5 max-w-xl text-lg leading-relaxed text-mute">{fest.tagline}</p></FadeUp>}
          <FadeUp delay={0.2} className="mt-8 flex flex-wrap items-center justify-center gap-3">
            {fest.status === "live" && <a href="#pass" className="inline-flex h-14 items-center gap-3 rounded-full bg-brand px-8 text-base font-semibold text-white shadow-[var(--shadow-glow)] transition hover:bg-brand-deep active:scale-[0.97]">Get your pass <Ticket className="h-5 w-5" /></a>}
            <ShareButtons title={fest.name} />
          </FadeUp>
        </div>
      </section>

      <div className="mx-auto max-w-7xl space-y-5 px-4 sm:px-6">
        <Reveal>
          <div className="card overflow-hidden p-3 sm:p-4">
            <div className="aspect-[16/9] overflow-hidden rounded-[1.25rem] sm:aspect-[21/9]"><PosterArt id={fest.id} title={fest.name} image={fest.banner_url} kicker="College fest" /></div>
          </div>
        </Reveal>

        <Reveal>{events === null ? <div className="card p-10 text-mute">We could not load the programme right now.</div> : <Programme events={events} />}</Reveal>

        <div className="grid gap-5 lg:grid-cols-2">
          <Reveal><EntryPassPanel slug={fest.slug} name={fest.name} isLive={fest.status === "live"} /></Reveal>
          <Reveal>
            <div className="card h-full p-8 sm:p-10">
              <h2 className="font-display text-3xl font-semibold tracking-tight">Venues</h2>
              {venues.length === 0 ? <p className="mt-3 text-mute">Venues will be announced with the programme.</p> : (
                <ul className="mt-5 space-y-3">{venues.map((v) => <li key={v} className="flex items-center gap-3 rounded-2xl bg-wash px-4 py-3"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-chip text-chip-ink"><MapPin className="h-4 w-4" /></span><span className="font-medium">{v}</span></li>)}</ul>
              )}
              <p className="mt-6 text-sm text-mute">Part of the <Link href="/fests" className="font-semibold text-brand">HiveOut</Link> fest network.</p>
            </div>
          </Reveal>
        </div>
      </div>
    </>
  );
}
