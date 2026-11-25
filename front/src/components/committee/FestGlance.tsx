"use client";

import { useEffect, useState } from "react";
import { CalendarDays, MapPin } from "lucide-react";
import { api, mediaSrc } from "@/lib/api";
import type { College, Contingent, ContingentSettings, FestManage, FestMeetingSummary, FestStats, FestTask, Org } from "@/lib/types";
import { daysLabel, formatDay } from "@/lib/format";
import { Pill } from "@/components/ui/bits";
import { Stat } from "@/components/admin/shared";
import { ReviewPill } from "./CommitteeShell";

interface Glance { org: Org | null; tasks: FestTask[] | null; meetings: FestMeetingSummary[] | null; colleges: ContingentSettings | null; contingents: Contingent[] | null; college: College | null }

/** The fest at a glance: what it is, when it runs, and the numbers that matter right now, each one a shortcut to where you act on it. */
/** The fest's banner. A missing one, or one that will not load, says so instead of leaving a broken picture. */
function BannerImage({ src }: { src: string | null }) {
  const [bad, setBad] = useState(false);
  if (src && !bad) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt="" onError={() => setBad(true)} className="h-full w-full object-cover" />;
  }
  return <div className="flex h-full items-center justify-center px-6 text-center text-sm text-mute">{src ? "The banner could not be loaded. Choose it again in Fest details." : "No banner yet. Add one in Fest details; it is the first thing students see."}</div>;
}

export function FestGlance({ fest, stats, goTo }: { fest: FestManage; stats: FestStats | null; goTo: (tab: string) => void }) {
  const [g, setG] = useState<Glance>({ org: null, tasks: null, meetings: null, colleges: null, contingents: null, college: null });

  useEffect(() => {
    let live = true;
    const slug = fest.slug;
    const ok = <T,>(p: Promise<T>) => p.then((v) => v).catch(() => null);
    Promise.all([
      ok(api<Org>(`/api/fests/${slug}/org`)), ok(api<FestTask[]>(`/api/fests/${slug}/tasks`)), ok(api<FestMeetingSummary[]>(`/api/fests/${slug}/meetings?when=upcoming`)),
      ok(api<ContingentSettings>(`/api/fests/${slug}/contingents/settings`)), ok(api<Contingent[]>(`/api/fests/${slug}/contingents`)), ok(api<College[]>("/api/colleges/")),
    ]).then(([org, tasks, meetings, colleges, contingents, all]) => { if (live) setG({ org, tasks, meetings, colleges, contingents, college: all?.find((c) => c.id === fest.college_id) ?? null }); });
    return () => { live = false; };
  }, [fest.slug, fest.college_id, fest.review_status, fest.status]);

  const banner = mediaSrc(fest.banner_url);
  const logo = mediaSrc(fest.logo_url);
  const days = fest.days_count;
  const dates = fest.start_date && fest.end_date
    ? `${fest.start_date === fest.end_date ? formatDay(fest.start_date) : `${formatDay(fest.start_date)} to ${formatDay(fest.end_date)}`}${days ? ` · ${daysLabel(days)}` : ""}`
    : fest.dates_tba ? "Dates coming soon" : "Dates not set yet";
  const open = (g.tasks ?? []).filter((t) => t.status !== "done");
  const overdue = open.filter((t) => t.overdue).length;
  const next = g.meetings?.[0];
  const waiting = (g.contingents ?? []).filter((c) => c.status === "pending").length;
  const pending = stats?.events.reduce((n, e) => n + e.pending, 0) ?? 0;
  const eventCount = stats?.events.length ?? 0;

  return (
    <section className="space-y-5" aria-label="Your fest at a glance">
      <div className="card overflow-hidden">
        <div className="relative aspect-[21/6] min-h-28 w-full bg-wash">
          <BannerImage src={banner} />
        </div>
        <div className="flex flex-wrap items-start gap-4 p-5 sm:p-6">
          {logo && /* eslint-disable-next-line @next/next/no-img-element */ <img src={logo} alt="" className="-mt-12 h-16 w-16 rounded-2xl bg-white object-cover shadow-[var(--shadow-card)] ring-4 ring-white sm:-mt-14 sm:h-20 sm:w-20" />}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2"><h2 className="font-display text-2xl font-bold tracking-tight">{fest.name}</h2><Pill tone={fest.status === "live" ? "green" : "neutral"}>{fest.status === "live" ? "Live" : "Not live"}</Pill><ReviewPill status={fest.review_status} /></div>
            {fest.tagline && <p className="mt-1 text-mute">{fest.tagline}</p>}
            <p className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-sm">
              <span className="inline-flex items-center gap-1.5"><CalendarDays className="h-4 w-4 text-mute" />{dates}</span>
              {g.college && <span className="inline-flex items-center gap-1.5"><MapPin className="h-4 w-4 text-mute" />{g.college.name}</span>}
              {fest.campus_address && <span className="text-mute">{fest.campus_address}</span>}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(11.5rem,1fr))]">
        <Stat label="Events" value={eventCount} hint={days ? `over ${daysLabel(days)}` : undefined} onClick={() => goTo("events")} />
        <Stat label="Entry passes" value={stats?.passes_issued ?? "…"} hint={stats ? `${stats.passes_checked_in} checked in` : undefined} />
        <Stat label="Registrations to approve" value={pending} tone="alert" onClick={pending ? () => goTo("registrations") : undefined} />
        <Stat label="Committee" value={g.org?.members.length ?? "…"} hint={g.org ? `${g.org.teams.length} team${g.org.teams.length === 1 ? "" : "s"}` : undefined} onClick={() => goTo("team")} />
        <Stat label="Open tasks" value={g.tasks ? open.length : "…"} hint={overdue ? `${overdue} overdue` : g.tasks ? "none overdue" : undefined} tone={overdue ? "alert" : "plain"} onClick={() => goTo("tasks")} />
        <Stat label="Next meeting" value={g.meetings ? (next ? formatDay(next.starts_at) : "None") : "…"} hint={next?.title} onClick={() => goTo("meetings")} />
        {g.colleges?.enabled && <Stat label="Visiting colleges" value={g.contingents?.length ?? "…"} hint={waiting ? `${waiting} waiting for you` : "none waiting"} tone={waiting ? "alert" : "plain"} onClick={() => goTo("colleges")} />}
      </div>
    </section>
  );
}
