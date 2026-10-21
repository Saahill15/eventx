import Link from "next/link";
import { ArrowRight, Building2, Users } from "lucide-react";
import { getAllEvents, getColleges, getLiveFests } from "@/lib/api";
import { isThisWeek, isUpcoming, formatDay } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { SectionHead } from "@/components/ui/bits";
import { Reveal, Stagger, StaggerItem, FadeUp } from "@/components/motion";
import { SearchLauncher } from "@/components/SearchLauncher";
import { HeroCarousel } from "@/components/HeroCarousel";
import { DateStrip } from "@/components/DateStrip";
import { PosterCard } from "@/components/Poster";
import { Rail, RailItem } from "@/components/Rail";
import { Marquee } from "@/components/Marquee";
import { Countdown } from "@/components/Countdown";
import { MiniTicket } from "@/components/home/MiniTicket";

export const revalidate = 30;

const VIBES = [
  { name: "Cultural", tint: "bg-peach" }, { name: "Technical", tint: "bg-sky" }, { name: "Music", tint: "bg-lilac" }, { name: "Sports", tint: "bg-mint" },
  { name: "Gaming", tint: "bg-butter" }, { name: "Design", tint: "bg-peach" }, { name: "Business", tint: "bg-sky" }, { name: "Literary", tint: "bg-lilac" },
];

export default async function Home() {
  const [fests, events, colleges] = await Promise.all([getLiveFests(), getAllEvents(), getColleges()]);
  const collegeName = (id: number | null) => colleges?.find((c) => c.id === id)?.name ?? null;

  const upcoming = (events ?? []).filter(isUpcoming).sort((a, b) => a.date.localeCompare(b.date));
  const thisWeek = upcoming.filter(isThisWeek);
  const rail = thisWeek.length > 0 ? thisWeek : upcoming;
  const free = upcoming.filter((e) => e.is_free || !e.price);
  const next = upcoming[0];
  const slides = (fests ?? []).slice(0, 5).map((f) => ({ id: f.id, slug: f.slug, name: f.name, tagline: f.tagline, banner: f.banner_url, college: collegeName(f.college_id), events: f.event_count }));
  const countOf = (cat: string) => upcoming.filter((e) => e.category === cat).length;

  return (
    <div className="mx-auto max-w-7xl px-5 sm:px-8">
      {/* Intro */}
      <section className="pb-8 pt-10 sm:pt-16">
        <FadeUp><p className="mb-4 text-xs font-bold uppercase tracking-[0.18em] text-amber-ink">College fest season</p></FadeUp>
        <FadeUp delay={0.06}>
          <h1 className="max-w-4xl font-display text-[2.9rem] font-bold leading-[0.98] tracking-[-0.03em] sm:text-7xl lg:text-[5.5rem]">
            Every fest.<br />Every event.<br /><span className="relative inline-block"><span className="relative z-10">One place.</span><span className="absolute inset-x-0 bottom-1 z-0 h-[0.38em] rounded-full bg-amber/80" /></span>
          </h1>
        </FadeUp>
        <FadeUp delay={0.14} className="mt-8 max-w-2xl"><SearchLauncher /></FadeUp>
      </section>

      {/* Featured fests */}
      <section className="pb-12">
        {slides.length > 0 ? <FadeUp delay={0.2}><HeroCarousel slides={slides} /></FadeUp> : (
          <div className="rounded-[2rem] bg-wash px-6 py-20 text-center">
            <p className="font-display text-2xl font-bold tracking-tight">{fests === null ? "We could not load fests right now" : "The first fests are being set up"}</p>
            <p className="mt-2 text-mute">{fests === null ? "Please check your connection and try again in a moment." : "Check back soon, or run a fest? Open the committee dashboard."}</p>
          </div>
        )}
      </section>

      {/* Pick a day */}
      <section className="py-6">
        <SectionHead kicker="Plan it" title="What is on, day by day" />
        <DateStrip />
      </section>

      {/* This week rail */}
      {rail.length > 0 && (
        <section className="pt-10">
          <SectionHead kicker={thisWeek.length > 0 ? "This week" : "Coming up"} title={thisWeek.length > 0 ? "Happening this week" : "Upcoming events"} action={<Link href="/events" className="hidden items-center gap-1 text-sm font-semibold sm:flex">See all <ArrowRight className="h-4 w-4" /></Link>} />
          <Rail label="Events this week">{rail.slice(0, 12).map((e) => <RailItem key={e.id}><PosterCard event={e} /></RailItem>)}</Rail>
        </section>
      )}

      {/* Bento */}
      <section className="pt-16">
        <SectionHead kicker="Why HiveOut" title="Built for fest season" />
        <Stagger className="grid auto-rows-[minmax(14rem,auto)] gap-4 md:grid-cols-6">
          <StaggerItem className="md:col-span-3 md:row-span-2">
            <div className="flex h-full flex-col justify-between overflow-hidden rounded-[2rem] bg-butter p-8">
              <div><p className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Walk in with a QR.</p><p className="mt-2 max-w-sm text-amber-ink">One pass per fest, one tap at the gate. No screenshots, no spreadsheets.</p></div>
              <div className="pt-8"><MiniTicket /></div>
            </div>
          </StaggerItem>
          <StaggerItem className="md:col-span-3">
            <div className="flex h-full flex-col justify-between rounded-[2rem] bg-lilac p-8">
              <p className="font-display text-3xl font-bold tracking-tight">One account, every fest.</p>
              <p className="max-w-sm text-violet-900/70">Sign up once. Register for events across colleges in a single tap.</p>
            </div>
          </StaggerItem>
          <StaggerItem className="md:col-span-1">
            <div className="flex h-full flex-col justify-between rounded-[2rem] bg-mint p-6"><p className="font-display text-6xl font-bold tracking-tight">₹0</p><p className="font-semibold text-emerald-900/70">Free for students</p></div>
          </StaggerItem>
          <StaggerItem className="md:col-span-2">
            {next ? (
              <Link href={`/events/${next.id}`} className="group flex h-full flex-col justify-between rounded-[2rem] bg-peach p-6 transition hover:shadow-[var(--shadow-pop)]">
                <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-orange-900/60">Next up</p><p className="mt-1 line-clamp-2 font-display text-xl font-bold leading-tight tracking-tight">{next.title}</p><p className="text-sm text-orange-900/60">{formatDay(next.date)}</p></div>
                <Countdown to={next.date} />
              </Link>
            ) : (
              <div className="flex h-full flex-col justify-between rounded-[2rem] bg-peach p-6"><p className="font-display text-xl font-bold">Events land here soon</p></div>
            )}
          </StaggerItem>
          <StaggerItem className="md:col-span-6">
            <div className="flex flex-col items-start justify-between gap-6 rounded-[2rem] bg-sky p-8 sm:flex-row sm:items-center">
              <div className="flex items-start gap-4"><span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white"><Users className="h-6 w-6 text-sky-900" /></span><div><p className="font-display text-2xl font-bold tracking-tight">Running a fest? Leave the spreadsheets behind.</p><p className="mt-1 max-w-xl text-sky-900/70">Publish events, take registrations, approve entries and manage your team from one dashboard. Free for colleges.</p></div></div>
              <Button href="/committee" variant="ink" size="lg">Open the dashboard</Button>
            </div>
          </StaggerItem>
        </Stagger>
      </section>

      {/* Vibes */}
      <section className="pt-16">
        <SectionHead kicker="Browse" title="Find your vibe" />
        <Stagger className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {VIBES.map((v) => (
            <StaggerItem key={v.name}>
              <Link href={`/events?category=${v.name}`} className={`group flex h-32 flex-col justify-between rounded-[1.5rem] ${v.tint} p-5 transition hover:-translate-y-1 hover:shadow-[var(--shadow-soft)] active:scale-[0.98]`}>
                <span className="font-display text-xl font-bold tracking-tight">{v.name}</span>
                <span className="flex items-center justify-between text-sm font-medium text-black/50">{countOf(v.name)} upcoming <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" /></span>
              </Link>
            </StaggerItem>
          ))}
        </Stagger>
      </section>

      {/* Free rail */}
      {free.length > 0 && (
        <section className="pt-16">
          <SectionHead kicker="No ticket needed" title="Free to attend" action={<Link href="/events?free=1" className="hidden items-center gap-1 text-sm font-semibold sm:flex">See all <ArrowRight className="h-4 w-4" /></Link>} />
          <Rail label="Free events">{free.slice(0, 12).map((e) => <RailItem key={e.id}><PosterCard event={e} /></RailItem>)}</Rail>
        </section>
      )}

      {/* Colleges */}
      {colleges && colleges.length > 0 && (
        <Reveal className="pt-16">
          <SectionHead kicker="Colleges" title="Fests from across the city" />
          <Marquee items={colleges.map((c) => c.name)} />
          <div className="mt-6 flex flex-wrap gap-2">
            {colleges.map((c) => <Link key={c.id} href={`/fests?college=${c.id}`} className="hairline inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold transition hover:bg-wash"><Building2 className="h-4 w-4 text-amber-ink" />{c.name}</Link>)}
          </div>
        </Reveal>
      )}

      {/* City teaser */}
      <Reveal className="pt-16">
        <div className="rounded-[2rem] border-2 border-dashed border-black/10 px-8 py-10 text-center">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-mute">Coming later</p>
          <p className="mt-2 font-display text-2xl font-bold tracking-tight">Concerts, gigs and city events are next.</p>
          <p className="mt-1 text-mute">We are starting with college fests. The same account will work for everything else.</p>
        </div>
      </Reveal>
    </div>
  );
}
