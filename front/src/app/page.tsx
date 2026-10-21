import Link from "next/link";
import { ArrowRight, Check } from "lucide-react";
import { getAllEvents, getColleges, getLiveFests } from "@/lib/api";
import { dayKey, formatDay, isUpcoming } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { Reveal, Stagger, StaggerItem } from "@/components/motion";
import { HeroShowcase } from "@/components/home/HeroShowcase";
import { PosterArt } from "@/components/Poster";
import { Programme } from "@/components/Programme";
import { FestPoster } from "@/components/FestPoster";
import { Faq } from "@/components/Faq";
import { SearchLauncher } from "@/components/SearchLauncher";
import { CategoryTabs } from "@/components/home/CategoryTabs";
import { CollegeCircles } from "@/components/home/CollegeCircles";
import { PosterCard } from "@/components/Poster";
import { Rail, RailItem } from "@/components/Rail";

export const revalidate = 30;

const VIBES = ["Cultural", "Technical", "Music", "Sports", "Gaming", "Design", "Business", "Literary", "Technology", "Education"];

const FAQ = [
  { q: "Is HiveOut really free?", a: "Yes. Students never pay to use HiveOut, and it is free for colleges and committees. Some fest events may have their own ticket price, which the organisers set." },
  { q: "How do I register for an event?", a: "Create a free account, open a fest and get your fest pass, then register for the events you want. Events that need approval show as waiting until the organisers confirm." },
  { q: "What is the QR pass?", a: "Each fest gives you one pass with a QR code. You will find it in My passes. Show it at the gate." },
  { q: "Can I pay for tickets here?", a: "Online payment is not live yet. For paid events the organisers will tell you how to pay." },
  { q: "I run a fest. How do I list it?", a: "Create an account, request organiser access from your profile, and then create your fest in the committee dashboard. Add your team, publish events and make the fest live when you are ready." },
  { q: "Will you list city events too?", a: "Yes, later. We are starting with college fests, and the same account will work for everything else." },
];

export default async function Home() {
  const [fests, events, colleges] = await Promise.all([getLiveFests(), getAllEvents(), getColleges()]);
  const collegeName = (id: number | null) => colleges?.find((c) => c.id === id)?.name ?? null;
  const upcoming = (events ?? []).filter(isUpcoming).sort((a, b) => a.date.localeCompare(b.date) || (a.time ?? "").localeCompare(b.time ?? ""));
  const firstFest = fests?.[0];
  const photo = firstFest ? { id: firstFest.id, title: firstFest.name, image: firstFest.banner_url } : upcoming[0] ? { id: upcoming[0].id, title: upcoming[0].title, image: upcoming[0].image_url } : null;

  // Next three days that have events, like an agenda
  const byDay = new Map<string, typeof upcoming>();
  for (const e of upcoming) { const k = dayKey(e.date); byDay.set(k, [...(byDay.get(k) ?? []), e]); }
  const agenda = Array.from(byDay.entries()).slice(0, 3);
  const showcase = (fests ?? []).slice(0, 3);

  return (
    <>
      <HeroShowcase photo={photo} />

      <div className="mx-auto max-w-7xl space-y-5 px-4 sm:px-6">
        <Reveal><div className="mx-auto max-w-2xl space-y-5"><SearchLauncher /><CategoryTabs /></div></Reveal>

        {/* Intro card with images */}
        <Reveal>
          <section className="card grid gap-8 overflow-hidden p-6 sm:p-10 lg:grid-cols-2">
            <div className="flex flex-col justify-center">
              <h2 className="font-display text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl">Find every fest happening around you</h2>
              <p className="mt-4 max-w-md text-lg text-mute">Browse fests by college, see the full programme and register for events without a spreadsheet in sight.</p>
              <div className="mt-6 flex flex-wrap gap-2.5">
                <span className="rounded-full bg-chip px-4 py-2 text-sm font-medium text-chip-ink">{(fests ?? []).length} live fest{(fests ?? []).length === 1 ? "" : "s"}</span>
                <span className="rounded-full bg-chip px-4 py-2 text-sm font-medium text-chip-ink">{upcoming.length} upcoming event{upcoming.length === 1 ? "" : "s"}</span>
              </div>
              <div className="mt-8"><Button href="/fests" size="lg">See all fests <ArrowRight className="h-5 w-5" /></Button></div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {showcase.length > 0 ? showcase.slice(0, 3).map((f, i) => (
                <Link key={f.id} href={`/fest/${f.slug}`} className={`group relative overflow-hidden rounded-3xl bg-wash transition hover:-translate-y-1 hover:shadow-[var(--shadow-pop)] ${i === 0 ? "col-span-2 aspect-[16/9]" : "aspect-square"}`}>
                  <div className="h-full w-full transition duration-700 group-hover:scale-105"><PosterArt id={f.id} title={f.name} image={f.banner_url} kicker="College fest" showTitle={false} /></div>
                  <div className="glass-photo absolute inset-x-2.5 bottom-2.5 rounded-2xl px-4 py-3"><p className="truncate font-display text-lg font-semibold">{f.name}</p></div>
                </Link>
              )) : <div className="col-span-2 flex aspect-[16/9] items-center justify-center rounded-3xl bg-wash text-mute">Fests appear here soon</div>}
            </div>
          </section>
        </Reveal>

        {/* Agenda card */}
        {agenda.length > 0 && (
          <Reveal>
            <section className="card p-6 sm:p-10">
              <h2 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">Coming up</h2>
              <ul className="mt-6 space-y-6">
                {agenda.map(([k, list]) => (
                  <li key={k} className="flex flex-col gap-3 sm:flex-row sm:items-start sm:gap-6">
                    <span className="inline-flex w-fit shrink-0 items-center rounded-2xl bg-chip px-5 py-3 text-lg font-medium text-chip-ink sm:w-36 sm:justify-center">{formatDay(k)}</span>
                    <p className="pt-1 text-lg leading-relaxed">
                      {list.map((e, i) => <span key={e.id}><Link href={`/events/${e.id}`} className="font-medium transition hover:text-chip-ink hover:underline">{e.title}</Link>{i < list.length - 1 ? ", " : ""}</span>)}
                    </p>
                  </li>
                ))}
              </ul>
              <div className="mt-8"><Link href="/events" className="inline-flex items-center gap-2 font-semibold text-chip-ink">See the full calendar <ArrowRight className="h-4 w-4" /></Link></div>
            </section>
          </Reveal>
        )}

        {/* This week, photo-led */}
        {upcoming.length > 0 && (
          <Reveal>
            <section className="card p-6 sm:p-10">
              <div className="mb-6 flex items-end justify-between gap-4"><h2 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">Happening soon</h2><Link href="/events" className="hidden items-center gap-1 font-semibold sm:flex">All events <ArrowRight className="h-4 w-4" /></Link></div>
              <Rail label="Happening soon">{upcoming.slice(0, 10).map((e) => <RailItem key={e.id}><PosterCard event={e} /></RailItem>)}</Rail>
            </section>
          </Reveal>
        )}

        {/* Vibes */}
        <Reveal>
          <section className="card p-6 sm:p-10">
            <h2 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">Pick your kind of fest</h2>
            <p className="mt-3 max-w-xl text-mute">Cultural nights, hackathons, gigs and sports. Jump straight to what you like.</p>
            <div className="mt-7 flex flex-wrap gap-3">
              {VIBES.map((v) => <Link key={v} href={`/events?category=${v}`} className="rounded-full bg-chip px-5 py-2.5 text-base font-medium text-chip-ink transition hover:bg-ink hover:text-white active:scale-95">{v}</Link>)}
            </div>
          </section>
        </Reveal>

        {/* Featured fests */}
        {(fests ?? []).length > 0 && (
          <section className="card p-6 sm:p-10">
            <div className="mb-6 flex items-end justify-between gap-4"><h2 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">Fests on HiveOut</h2><Link href="/fests" className="hidden items-center gap-1 font-semibold text-chip-ink sm:flex">All fests <ArrowRight className="h-4 w-4" /></Link></div>
            <Stagger className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
              {(fests ?? []).slice(0, 8).map((f) => <StaggerItem key={f.id}><FestPoster fest={f} college={collegeName(f.college_id)} /></StaggerItem>)}
            </Stagger>
          </section>
        )}

        {/* Programme preview */}
        {upcoming.length > 0 && <Reveal><Programme events={upcoming.slice(0, 12)} title="What is on" /></Reveal>}

        {/* Colleges */}
        {colleges && colleges.length > 0 && <Reveal><CollegeCircles colleges={colleges} /></Reveal>}

        {/* Plans */}
        <Reveal>
          <section className="card p-6 sm:p-10">
            <h2 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">Join HiveOut</h2>
            <p className="mt-3 max-w-xl text-mute">Free for students and free for committees. No card, no catch.</p>
            <Stagger className="mt-8 grid gap-4 md:grid-cols-3">
              {[
                { name: "Students", price: "Free", points: ["Browse every fest", "One-tap registration", "QR pass in your pocket"], cta: "Create an account", href: "/signup", main: true },
                { name: "Committees", price: "Free", points: ["Publish events", "Approve registrations", "Manage your team"], cta: "Open the dashboard", href: "/committee", main: false },
                { name: "City events", price: "Soon", points: ["Concerts and gigs", "Same HiveOut account", "Coming after fests"], cta: "Stay tuned", href: "/events", main: false },
              ].map((p) => (
                <StaggerItem key={p.name}>
                  <div className={`flex h-full flex-col rounded-3xl p-7 ${p.main ? "bg-ink text-white" : "bg-wash"}`}>
                    <p className={`text-sm font-semibold ${p.main ? "text-brand" : "text-mute"}`}>{p.name}</p>
                    <p className="mt-1 font-display text-5xl font-semibold tracking-tight">{p.price}</p>
                    <ul className="mt-6 flex-1 space-y-3">{p.points.map((pt) => <li key={pt} className="flex items-center gap-2.5"><Check className={`h-4 w-4 ${p.main ? "text-brand" : "text-ink"}`} />{pt}</li>)}</ul>
                    <Link href={p.href} className={`mt-8 inline-flex h-12 items-center justify-center rounded-full text-[0.9375rem] font-semibold transition active:scale-[0.97] ${p.main ? "bg-white text-ink hover:bg-chip" : "bg-white text-ink shadow-[var(--shadow-card)] hover:bg-chip"}`}>{p.cta}</Link>
                  </div>
                </StaggerItem>
              ))}
            </Stagger>
          </section>
        </Reveal>

        {/* FAQ */}
        <Reveal>
          <section className="card p-6 sm:p-10">
            <h2 className="mb-2 font-display text-3xl font-semibold tracking-tight sm:text-4xl">Questions, answered</h2>
            <Faq items={FAQ} />
          </section>
        </Reveal>

        {/* Final CTA */}
        <Reveal>
          <section className="dots relative overflow-hidden rounded-[1.5rem] bg-ink px-6 py-16 text-center text-white">
            <div className="absolute inset-0 bg-ink/95" aria-hidden />
            <div className="relative">
              <h2 className="mx-auto max-w-2xl font-display text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">Join us this fest season</h2>
              <p className="mx-auto mt-4 max-w-md text-lg text-white/70">Get your free pass and never miss an event.</p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Link href="/signup" className="inline-flex h-14 items-center rounded-full bg-brand px-8 font-semibold text-on-brand transition hover:bg-brand-deep active:scale-[0.97]">Join free</Link>
                <Link href="/fests" className="inline-flex h-14 items-center rounded-full bg-white/10 px-8 font-semibold text-white ring-1 ring-white/30 transition hover:bg-white/20 active:scale-[0.97]">Explore fests</Link>
              </div>
            </div>
          </section>
        </Reveal>
      </div>
    </>
  );
}
