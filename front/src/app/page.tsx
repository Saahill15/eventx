import Link from "next/link";
import { ArrowRight, Building2, CalendarCheck, Compass, QrCode, Users } from "lucide-react";
import { getAllEvents, getColleges, getLiveFests } from "@/lib/api";
import { isThisWeek, isUpcoming } from "@/lib/format";
import { Hero } from "@/components/Hero";
import { Reveal, Stagger, StaggerItem } from "@/components/motion";
import { FestCard } from "@/components/FestCard";
import { EventCard } from "@/components/EventCard";
import { Button } from "@/components/ui/Button";
import { SectionHeading } from "@/components/ui/bits";

export const revalidate = 30;

const CATEGORIES = ["Cultural", "Technical", "Music", "Sports", "Gaming", "Design", "Business", "Literary"];

export default async function Home() {
  const [fests, events, colleges] = await Promise.all([getLiveFests(), getAllEvents(), getColleges()]);
  const collegeName = (id: number | null) => colleges?.find((c) => c.id === id)?.name ?? null;

  const liveFests = fests ?? [];
  const upcoming = (events ?? []).filter(isUpcoming).sort((a, b) => a.date.localeCompare(b.date));
  const thisWeek = upcoming.filter(isThisWeek);
  const spotlight = thisWeek.length > 0 ? thisWeek : upcoming;
  const featured = liveFests[0];
  const others = liveFests.slice(1, 4);

  return (
    <>
      <Hero />

      {/* Featured fests */}
      <section className="mx-auto max-w-6xl px-6 py-10">
        <SectionHeading
          eyebrow="Featured"
          title="Fests on HiveOut"
          action={<Link href="/fests" className="flex items-center gap-1 text-sm font-semibold text-hive-ink">See all <ArrowRight className="h-4 w-4" /></Link>}
        />
        {featured ? (
          <Stagger className="grid gap-5 lg:grid-cols-3">
            <StaggerItem className="lg:col-span-2"><FestCard fest={featured} collegeName={collegeName(featured.college_id)} large /></StaggerItem>
            <div className="grid gap-5">
              {others.slice(0, 2).map((f) => <StaggerItem key={f.id}><FestCard fest={f} collegeName={collegeName(f.college_id)} /></StaggerItem>)}
            </div>
          </Stagger>
        ) : (
          <div className="glass rounded-3xl px-6 py-14 text-center text-neutral-500">
            {fests === null ? "We could not load fests right now. Please try again in a moment." : "The first fests are being set up. Check back soon."}
          </div>
        )}
      </section>

      {/* Happening soon */}
      {spotlight.length > 0 && (
        <section className="mx-auto max-w-6xl px-6 py-10">
          <SectionHeading
            eyebrow={thisWeek.length > 0 ? "This week" : "Coming up"}
            title={thisWeek.length > 0 ? "Happening this week" : "Upcoming events"}
            action={<Link href="/events" className="flex items-center gap-1 text-sm font-semibold text-hive-ink">All events <ArrowRight className="h-4 w-4" /></Link>}
          />
          <Stagger className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {spotlight.slice(0, 6).map((e) => <StaggerItem key={e.id}><EventCard event={e} /></StaggerItem>)}
          </Stagger>
        </section>
      )}

      {/* Categories */}
      <section className="mx-auto max-w-6xl px-6 py-10">
        <SectionHeading eyebrow="Browse" title="Find your thing" />
        <Stagger className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {CATEGORIES.map((c) => (
            <StaggerItem key={c}>
              <Link href={`/events?category=${c}`} className="glass block rounded-2xl px-5 py-5 text-base font-semibold transition hover:-translate-y-0.5 hover:bg-white/90 active:scale-[0.98]">
                {c}
              </Link>
            </StaggerItem>
          ))}
        </Stagger>
      </section>

      {/* Colleges */}
      {colleges && colleges.length > 0 && (
        <section className="mx-auto max-w-6xl px-6 py-10">
          <SectionHeading eyebrow="Colleges" title="Browse by college" />
          <div className="flex flex-wrap gap-3">
            {colleges.map((c) => (
              <Link key={c.id} href={`/fests?college=${c.id}`} className="glass flex items-center gap-2 rounded-full px-5 py-3 text-sm font-semibold transition hover:bg-white/90">
                <Building2 className="h-4 w-4 text-hive-ink" /> {c.name}
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* How it works */}
      <section className="mx-auto max-w-6xl px-6 py-14">
        <SectionHeading eyebrow="How it works" title="From discovery to the gate" />
        <Stagger className="grid gap-5 sm:grid-cols-3">
          {[
            { icon: Compass, title: "Find", body: "Browse fests and events by college, date and category. Everything is in one place." },
            { icon: CalendarCheck, title: "Register", body: "Create a free account once. Get a fest pass and register for events in a tap." },
            { icon: QrCode, title: "Walk in", body: "Show your QR pass at the gate. No screenshots, no spreadsheets, no waiting." },
          ].map(({ icon: Icon, title, body }, i) => (
            <StaggerItem key={title} className="glass rounded-3xl p-7">
              <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-2xl bg-hive-50 text-hive-ink"><Icon className="h-5 w-5" /></div>
              <p className="text-xs font-bold text-neutral-400">STEP {i + 1}</p>
              <h3 className="mt-1 font-display text-xl font-extrabold tracking-tight">{title}</h3>
              <p className="mt-2 leading-relaxed text-neutral-500">{body}</p>
            </StaggerItem>
          ))}
        </Stagger>
      </section>

      {/* For committees */}
      <section className="mx-auto max-w-6xl px-6 py-10">
        <Reveal className="glass-strong relative overflow-hidden rounded-[2rem] px-8 py-12 text-center sm:px-16">
          <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-hive/20 blur-3xl" />
          <Users className="mx-auto h-8 w-8 text-hive-ink" />
          <h2 className="mx-auto mt-4 max-w-xl font-display text-3xl font-extrabold tracking-tight sm:text-4xl">Running a fest? Leave the spreadsheets behind.</h2>
          <p className="mx-auto mt-3 max-w-lg text-neutral-500">
            Publish events, take registrations, approve entries, and manage your whole team from one dashboard. Free for colleges.
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Button href="/committee" size="lg">Open the committee dashboard</Button>
          </div>
        </Reveal>
      </section>

      {/* City teaser */}
      <section className="mx-auto max-w-6xl px-6 pb-4 pt-10">
        <Reveal className="glass rounded-3xl px-8 py-8 text-center">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-neutral-400">Coming later</p>
          <p className="mt-2 font-display text-xl font-extrabold tracking-tight">Concerts, gigs and city events are next.</p>
          <p className="mt-1 text-neutral-500">We are starting with college fests. The same account will work for everything else.</p>
        </Reveal>
      </section>
    </>
  );
}
