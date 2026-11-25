"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, CalendarDays, CheckCircle2, Users } from "lucide-react";
import { api, mediaSrc } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canHostFests } from "@/lib/permissions";
import type { DashAttention, DashFest, DashTask, DashUpcoming, Dashboard } from "@/lib/types";
import { daysLabel, formatDay, formatTime } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, Pill, Skeleton } from "@/components/ui/bits";
import { greeting, PageHeader } from "@/components/shell/WorkspaceShell";
import { ReviewPill } from "./CommitteeShell";
import { IncomingTransfers } from "./IncomingTransfers";

const ROLE: Record<string, string> = { owner: "Festival director", core: "Core team", volunteer: "Volunteer", admin: "Admin view" };
const DOT: Record<string, string> = { red: "bg-red-500", amber: "bg-amber-500", green: "bg-emerald-500" };
const dateOnly = (iso: string) => iso.slice(0, 10);

/** "Today", "Tomorrow", or "Wed, 2 Dec": how far away a day is, in words. */
function dayHeading(iso: string): string {
  const d = new Date(`${dateOnly(iso)}T00:00:00`);
  const today = new Date(new Date().setHours(0, 0, 0, 0));
  const diff = Math.round((d.getTime() - today.getTime()) / 86_400_000);
  return diff <= 0 ? "Today" : diff === 1 ? "Tomorrow" : formatDay(dateOnly(iso));
}

const go = (slug: string, tab: string) => `/dashboard/fests/${slug}#${tab}`;

/** Everything waiting on this person, most urgent first. One row, one click to where it gets done. */
function NeedsYou({ items }: { items: DashAttention[] }) {
  if (items.length === 0) {
    return <div className="card flex items-center gap-3 px-5 py-4"><CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" /><p className="text-[14px]"><span className="font-semibold">You are all caught up.</span> <span className="text-mute">Nothing is waiting for you.</span></p></div>;
  }
  return (
    <section className="card overflow-hidden" aria-label="Needs you">
      <div className="flex h-12 items-center border-b border-[var(--ws-border)] px-5"><h2 className="text-[14px] font-semibold">Needs you <span className="ml-1 font-normal text-mute">{items.length}</span></h2></div>
      <ul>
        {items.map((a, i) => (
          <li key={`${a.kind}-${a.fest_slug}-${i}`} className="border-b border-[var(--ws-border)] last:border-b-0">
            <Link href={go(a.fest_slug, a.tab)} className="flex items-start gap-3 px-5 py-3.5 transition hover:bg-black/[0.02]">
              <span aria-hidden className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${DOT[a.tone]}`} />
              <span className="min-w-0 flex-1">
                <span className="block text-[14px] font-semibold">{a.title}</span>
                <span className="block truncate text-[13px] text-mute">{a.fest_name}{a.detail ? ` · ${a.detail}` : ""}</span>
              </span>
              <span className="mt-0.5 hidden shrink-0 items-center gap-1 text-[13px] font-semibold sm:inline-flex">Open <ArrowRight className="h-3.5 w-3.5" /></span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** The fest's banner, or nothing (the tinted block shows through) when there is none or it will not load. */
function Banner({ src }: { src: string | null }) {
  const [bad, setBad] = useState(false);
  // eslint-disable-next-line @next/next/no-img-element
  return src && !bad ? <img src={src} alt="" onError={() => setBad(true)} className="h-full w-full object-cover" /> : null;
}

function Tile({ label, value, alert }: { label: string; value: number | null; alert?: boolean }) {
  return (
    <div className="rounded-lg bg-wash px-3 py-2.5">
      <p className="text-[12px] text-mute">{label}</p>
      <p className={`text-[20px] font-semibold leading-tight ${alert && (value ?? 0) > 0 ? "text-[var(--ws-accent)]" : ""}`}>{value ?? "–"}</p>
    </div>
  );
}

function FestCard({ f }: { f: DashFest }) {
  const banner = mediaSrc(f.banner_url);
  const staff = f.my_role === "owner" || f.my_role === "core" || f.my_role === "admin";
  const live = f.status === "live";
  const when = f.dates_tba && !f.start_date ? "Dates coming soon" : f.start_date ? `${formatDay(f.start_date)}${f.end_date && f.end_date !== f.start_date ? ` to ${formatDay(f.end_date)}` : ""}${f.days_count ? ` · ${daysLabel(f.days_count)}` : ""}` : "No dates yet";
  const pct = f.setup ? Math.round((f.setup.done / Math.max(f.setup.total, 1)) * 100) : 0;
  return (
    <article className="card flex flex-col overflow-hidden">
      <Link href={`/dashboard/fests/${f.slug}`} className="block" aria-label={`Open ${f.name}`}>
        <div className="relative h-24 bg-gradient-to-br from-teal-50 to-emerald-100">
          <Banner src={banner} />
          <div className="absolute left-3 top-3 flex gap-1.5">{live ? <Pill tone="green">Live</Pill> : <ReviewPill status={f.review_status} />}</div>
        </div>
      </Link>
      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="min-w-0">
          <Link href={`/dashboard/fests/${f.slug}`} className="block truncate text-[16px] font-semibold hover:underline">{f.name}</Link>
          <p className="truncate text-[13px] text-mute">{ROLE[f.my_role]}{f.college_name ? ` · ${f.college_name}` : ""}</p>
          <p className="mt-0.5 flex items-center gap-1.5 text-[13px] text-mute"><CalendarDays className="h-3.5 w-3.5" />{when}</p>
        </div>

        {f.setup ? (
          <div>
            <div className="mb-1.5 flex items-center justify-between text-[13px]"><span className="font-medium">Setup</span><span className="text-mute">{f.setup.done} of {f.setup.total} done</span></div>
            <div className="h-1.5 overflow-hidden rounded-full bg-black/[0.07]" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Setup progress"><div className="h-full rounded-full bg-[var(--ws-accent)] transition-all" style={{ width: `${pct}%` }} /></div>
            {f.setup.next_label && f.setup.next_tab && <Link href={go(f.slug, f.setup.next_tab)} className="mt-2.5 inline-flex items-center gap-1 text-[13px] font-semibold hover:underline">Next: {f.setup.next_label} <ArrowRight className="h-3.5 w-3.5" /></Link>}
          </div>
        ) : staff ? (
          <div className="grid grid-cols-2 gap-2">
            <Tile label="Events" value={f.events} /><Tile label="Registered" value={f.registered} /><Tile label="To approve" value={f.pending} alert /><Tile label="Entry passes" value={f.passes_issued} />
          </div>
        ) : (
          <p className="text-[13px] text-mute">You help run this fest. Your tasks and check-in are inside.</p>
        )}

        <div className="mt-auto flex flex-wrap gap-x-4 gap-y-1 border-t border-[var(--ws-border)] pt-3 text-[13px] font-semibold">
          {staff ? (
            <>
              <Link href={go(f.slug, "events")} className="hover:underline">Events</Link>
              <Link href={go(f.slug, "registrations")} className="hover:underline">Registrations</Link>
              <Link href={go(f.slug, "team")} className="inline-flex items-center gap-1 hover:underline"><Users className="h-3.5 w-3.5" />Committee</Link>
              {live && <Link href={`/fests/${f.slug}`} className="ml-auto text-mute hover:text-ink">Public page ↗</Link>}
            </>
          ) : <Link href={`/dashboard/fests/${f.slug}`} className="hover:underline">Open</Link>}
        </div>
      </div>
    </article>
  );
}

/** What is happening in the next two weeks, grouped by day, events and meetings together. */
function ComingUp({ items }: { items: DashUpcoming[] }) {
  const groups: { day: string; rows: DashUpcoming[] }[] = [];
  for (const u of items) {
    const key = dayHeading(u.when);
    const g = groups.find((x) => x.day === key);
    if (g) g.rows.push(u); else groups.push({ day: key, rows: [u] });
  }
  return (
    <section className="card overflow-hidden" aria-label="Coming up">
      <div className="flex h-12 items-center border-b border-[var(--ws-border)] px-5"><h2 className="text-[14px] font-semibold">Next two weeks</h2></div>
      {items.length === 0 ? <p className="px-5 py-8 text-center text-[14px] text-mute">No events or meetings in the next two weeks.</p> : (
        <div className="divide-y divide-[var(--ws-border)]">
          {groups.map((g) => (
            <div key={g.day} className="px-5 py-3">
              <p className="mb-1.5 text-[12px] font-semibold uppercase tracking-wider text-mute">{g.day}</p>
              <ul className="space-y-2">
                {g.rows.map((u, i) => (
                  <li key={`${u.kind}-${u.title}-${i}`}>
                    <Link href={go(u.fest_slug, u.tab)} className="flex items-start gap-3 rounded-md hover:bg-black/[0.02]">
                      <span className="w-[4.5rem] shrink-0 pt-0.5 text-[13px] tabular-nums text-mute">{u.time ? formatTime(u.time) : "All day"}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[14px] font-medium">{u.title}</span>
                        <span className="block truncate text-[13px] text-mute">{u.kind === "meeting" ? "Meeting" : "Event"} · {u.fest_name}{u.detail ? ` · ${u.detail}` : ""}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function MyTasks({ items }: { items: DashTask[] }) {
  return (
    <section className="card overflow-hidden" aria-label="Your tasks">
      <div className="flex h-12 items-center justify-between border-b border-[var(--ws-border)] px-5"><h2 className="text-[14px] font-semibold">Your tasks <span className="ml-1 font-normal text-mute">{items.length}</span></h2></div>
      {items.length === 0 ? <p className="px-5 py-8 text-center text-[14px] text-mute">Nothing is assigned to you.</p> : (
        <ul>
          {items.map((t) => (
            <li key={t.id} className="border-b border-[var(--ws-border)] last:border-b-0">
              <Link href={go(t.fest_slug, "tasks")} className="flex items-start justify-between gap-3 px-5 py-3 hover:bg-black/[0.02]">
                <span className="min-w-0"><span className="block truncate text-[14px] font-medium">{t.title}</span><span className="block truncate text-[13px] text-mute">{t.fest_name}</span></span>
                <span className={`shrink-0 text-[13px] ${t.overdue ? "font-semibold text-red-600" : "text-mute"}`}>{t.due_date ? `${t.overdue ? "Overdue · " : "Due "}${formatDay(t.due_date)}` : "No date"}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function CommitteeOverview() {
  const { user } = useAuth();
  const [data, setData] = useState<Dashboard | null>(null);
  const [failed, setFailed] = useState(false);
  const canCreate = canHostFests(user);

  useEffect(() => { api<Dashboard>("/api/dashboard").then(setData).catch(() => setFailed(true)); }, []);

  if (failed) return <div className="space-y-4"><PageHeader title={greeting(user?.first_name)} /><EmptyState title="Could not load your dashboard" body="Check your connection and refresh the page." /></div>;
  if (!data) return <div className="space-y-4"><Skeleton className="h-12 w-72" /><Skeleton className="h-28" /><div className="grid gap-4 md:grid-cols-2"><Skeleton className="h-64" /><Skeleton className="h-64" /></div></div>;

  const newFest = canCreate ? <Button href="/dashboard/fests#new" size="sm">New fest</Button> : null;

  if (data.fests.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title={greeting(user?.first_name)} sub={canCreate ? "Create your first fest to get started." : "You are not on a fest team yet."} />
        <IncomingTransfers />
        <EmptyState
          title={canCreate ? "No fests yet" : "You are not on a fest committee"}
          body={canCreate ? "Create your first fest, fill in its details, add events and send it to HiveOut for review." : "Committee tools appear here once you are added to a fest team."}
          action={canCreate ? <Button href="/dashboard/fests#new">Create a fest</Button> : undefined}
        />
      </div>
    );
  }

  const n = data.attention.length;
  const sub = n > 0 ? `${n} thing${n === 1 ? "" : "s"} need${n === 1 ? "s" : ""} you.` : data.coming_up.length > 0 ? `Nothing is waiting for you. ${data.coming_up.length} thing${data.coming_up.length === 1 ? "" : "s"} coming up.` : "Nothing is waiting for you.";

  return (
    <div className="space-y-6">
      <PageHeader title={greeting(user?.first_name)} sub={sub} actions={<>{newFest}<Button href="/dashboard/fests" variant="outline" size="sm">All fests</Button></>} />
      <IncomingTransfers />
      <NeedsYou items={data.attention} />

      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section aria-label="Your fests" className="min-w-0">
          <div className="mb-3 flex items-center justify-between"><h2 className="text-[14px] font-semibold">Your fests <span className="ml-1 font-normal text-mute">{data.fests.length}</span></h2></div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">{data.fests.map((f) => <FestCard key={f.id} f={f} />)}</div>
        </section>
        <div className="min-w-0 space-y-6">
          <ComingUp items={data.coming_up} />
          <MyTasks items={data.my_tasks} />
        </div>
      </div>
    </div>
  );
}
