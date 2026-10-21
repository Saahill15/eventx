import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Building2, CalendarDays } from "lucide-react";
import { getColleges, getFestBySlug, getFestEvents } from "@/lib/api";
import { FestArt } from "@/components/EventArt";
import { EntryPassPanel } from "@/components/EntryPassPanel";
import { FestSchedule } from "@/components/FestSchedule";
import { ShareButtons } from "@/components/ShareButtons";

type Props = { params: Promise<{ slug: string }> };
export const revalidate = 30;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const f = await getFestBySlug(slug);
  if (!f) return { title: "Fest not found" };
  const description = f.tagline ?? `Events, schedule and registration for ${f.name} on HiveOut.`;
  return { title: f.name, description, openGraph: { title: f.name, description, type: "website" } };
}

export default async function FestPage({ params }: Props) {
  const { slug } = await params;
  const [fest, events, colleges] = await Promise.all([getFestBySlug(slug), getFestEvents(slug), getColleges()]);
  if (!fest) notFound();
  const college = colleges?.find((c) => c.id === fest.college_id);

  return (
    <div className="mx-auto max-w-6xl px-6 pb-8 pt-4">
      <div className="relative isolate overflow-hidden rounded-[2rem]">
        <div className="h-[22rem] sm:h-[26rem]">
          <FestArt src={fest.banner_url} />
        </div>
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
        <div className="absolute inset-x-0 bottom-0 p-4 sm:p-6">
          <div className="glass-strong flex flex-col gap-4 rounded-3xl p-5 sm:flex-row sm:items-end sm:justify-between sm:p-7">
            <div>
              {college && <p className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-hive-ink"><Building2 className="h-4 w-4" /> {college.name}</p>}
              <h1 className="font-display text-3xl font-black leading-tight tracking-tight sm:text-5xl">{fest.name}</h1>
              {fest.tagline && <p className="mt-2 max-w-xl text-neutral-600">{fest.tagline}</p>}
              <p className="mt-3 flex items-center gap-2 text-sm font-medium text-neutral-500"><CalendarDays className="h-4 w-4" />{fest.event_count} event{fest.event_count === 1 ? "" : "s"}</p>
            </div>
            <ShareButtons title={fest.name} />
          </div>
        </div>
      </div>

      <div className="mt-6"><EntryPassPanel slug={fest.slug} isLive={fest.status === "live"} /></div>

      <section className="mt-14">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-hive-ink">Schedule</p>
        <h2 className="mb-6 mt-1 font-display text-3xl font-extrabold tracking-tight">What is on</h2>
        {events === null ? <p className="text-neutral-500">We could not load the schedule right now.</p> : <FestSchedule events={events} />}
      </section>

      <p className="mt-16 text-center text-sm text-neutral-400">Part of the <Link href="/fests" className="font-semibold hover:text-ink">HiveOut</Link> fest network</p>
    </div>
  );
}
