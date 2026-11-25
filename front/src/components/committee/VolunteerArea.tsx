"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Dashboard, FestEvent, FestMeetingDetail, FestMeetingSummary, MyFest } from "@/lib/types";
import { formatDay, formatTime } from "@/lib/format";
import { EmptyState, Pill, Skeleton } from "@/components/ui/bits";
import { SubTabs } from "@/components/ui/SubTabs";
import { GateTab } from "./GateTab";
import { MySpendPanel } from "./FinanceSpend";
import { MyTeamPanel } from "./MyTeamPanel";
import { ShiftsTab } from "./ShiftsTab";
import { TasksTab } from "./TasksTab";

type Id = "home" | "duty" | "meetings" | "tasks" | "spend" | "gate";
const ITEMS: { id: Id; label: string }[] = [
  { id: "home", label: "Home" }, { id: "duty", label: "My duty" }, { id: "meetings", label: "Meetings" }, { id: "tasks", label: "My tasks" }, { id: "spend", label: "Spending" }, { id: "gate", label: "Check-in" },
];
const ALIAS: Record<string, Id> = { shifts: "duty", gate: "gate", tasks: "tasks", meetings: "meetings", finance: "spend" };
const when = (iso: string) => `${formatDay(iso)}, ${formatTime(iso.slice(11, 16))}`;

/** A volunteer's view of one meeting: the agenda before, the minutes and action items after. They can read, not change. */
function MeetingRead({ slug, id }: { slug: string; id: number }) {
  const [m, setM] = useState<FestMeetingDetail | null>(null);
  useEffect(() => { api<FestMeetingDetail>(`/api/fests/${slug}/meetings/${id}`).then(setM).catch(() => {}); }, [slug, id]);
  if (!m) return <Skeleton className="mt-3 h-20" />;
  return (
    <div className="mt-3 space-y-3 border-t border-black/5 pt-3 text-sm">
      {m.agenda && <div><p className="font-semibold">Agenda</p><p className="whitespace-pre-line text-mute">{m.agenda}</p></div>}
      {m.minutes && <div><p className="font-semibold">What was decided</p><p className="whitespace-pre-line text-mute">{m.minutes}</p></div>}
      {m.actions.length > 0 && <div><p className="font-semibold">Action items</p><ul className="text-mute">{m.actions.map((a) => <li key={a.id}>{a.status === "done" ? "Done" : "To do"}: {a.title}{a.assignee_name ? ` (${a.assignee_name})` : ""}</li>)}</ul></div>}
      {!m.agenda && !m.minutes && m.actions.length === 0 && <p className="text-mute">Nothing written down for this one yet.</p>}
      <p className="text-[13px] text-mute">{m.attendees.length} invited{m.attendees.some((a) => a.attended) ? `, ${m.attendees.filter((a) => a.attended).length} came` : ""}</p>
    </div>
  );
}

function MyMeetings({ slug }: { slug: string }) {
  const [view, setView] = useState<"upcoming" | "past">("upcoming");
  const [rows, setRows] = useState<FestMeetingSummary[] | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  useEffect(() => { setRows(null); api<FestMeetingSummary[]>(`/api/fests/${slug}/meetings?when=${view}`).then(setRows).catch(() => setRows([])); }, [slug, view]);
  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex gap-2" role="group" aria-label="Which meetings">{(["upcoming", "past"] as const).map((w) => <button key={w} aria-pressed={view === w} onClick={() => setView(w)} className={`rounded-full px-4 py-2 text-sm font-semibold capitalize transition ${view === w ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)] hover:text-ink"}`}>{w}</button>)}</div>
      {rows === null ? <Skeleton className="h-24" /> : rows.length === 0 ? <EmptyState title={view === "upcoming" ? "No meetings coming up" : "No past meetings"} body="When the core team schedules one, you are told and it shows here with its agenda." /> : (
        <ul className="space-y-3">{rows.map((m) => (
          <li key={m.id} className="card p-5">
            <div className="flex flex-wrap items-center justify-between gap-3"><div className="min-w-0"><p className="font-semibold">{m.title}</p><p className="text-sm text-mute">{when(m.starts_at)}{m.location ? ` · ${m.location}` : ""}</p></div>
              <button onClick={() => setOpen(open === m.id ? null : m.id)} className="text-sm font-semibold underline underline-offset-4">{open === m.id ? "Hide" : view === "past" ? "Minutes" : "Agenda"}</button></div>
            {open === m.id && <MeetingRead slug={slug} id={m.id} />}
          </li>
        ))}</ul>
      )}
    </div>
  );
}

function Home({ slug, go }: { slug: string; go: (id: Id) => void }) {
  const [d, setD] = useState<Dashboard | null>(null);
  useEffect(() => { api<Dashboard>("/api/dashboard").then(setD).catch(() => setD({ fests: [], attention: [], my_tasks: [], coming_up: [] })); }, []);
  if (!d) return <Skeleton className="h-48" />;
  const next = d.coming_up.filter((u) => u.fest_slug === slug && u.kind !== "event");
  const tasks = d.my_tasks.filter((t) => t.fest_slug === slug);
  const alerts = d.attention.filter((a) => a.fest_slug === slug);
  const target = (tab: string): Id => ALIAS[tab] ?? (tab as Id);
  return (
    <div className="grid max-w-5xl gap-5 lg:grid-cols-2">
      {alerts.length > 0 && <div className="space-y-2 lg:col-span-2">{alerts.map((a, i) => <button key={i} onClick={() => go(target(a.tab))} className="card flex w-full items-center justify-between gap-3 p-4 text-left"><span><span className="font-semibold">{a.title}</span>{a.detail && <span className="block text-sm text-mute">{a.detail}</span>}</span><Pill tone={a.tone === "red" ? "red" : "amber"}>Look</Pill></button>)}</div>}
      <section className="card p-5" aria-label="Coming up">
        <div className="mb-3 flex items-center justify-between"><h2 className="text-[15px] font-semibold">Coming up for you</h2><button onClick={() => go("duty")} className="text-[13px] font-semibold underline underline-offset-4">All duties</button></div>
        {next.length === 0 ? <p className="text-sm text-mute">No duties or meetings in the next two weeks.</p> : (
          <ul className="divide-y divide-black/5">{next.map((u, i) => <li key={i} className="flex items-center justify-between gap-3 py-2.5"><div className="min-w-0"><p className="truncate font-semibold">{u.title}</p><p className="text-sm text-mute">{u.detail ?? ""}</p></div><div className="shrink-0 text-right text-sm"><p className="font-semibold">{formatDay(u.when.slice(0, 10))}</p>{u.time && <p className="text-mute">{formatTime(u.time)}</p>}</div></li>)}</ul>
        )}
      </section>
      <section className="card p-5" aria-label="My tasks">
        <div className="mb-3 flex items-center justify-between"><h2 className="text-[15px] font-semibold">Your tasks</h2><button onClick={() => go("tasks")} className="text-[13px] font-semibold underline underline-offset-4">All tasks</button></div>
        {tasks.length === 0 ? <p className="text-sm text-mute">Nothing assigned to you.</p> : (
          <ul className="divide-y divide-black/5">{tasks.slice(0, 5).map((t) => <li key={t.id} className="flex items-center justify-between gap-3 py-2.5"><span className="truncate font-semibold">{t.title}</span><span className="shrink-0 text-sm">{t.overdue ? <Pill tone="red">Overdue</Pill> : t.due_date ? <span className="text-mute">due {formatDay(t.due_date)}</span> : null}</span></li>)}</ul>
        )}
      </section>
      <div className="lg:col-span-2"><MyTeamPanel slug={slug} /></div>
    </div>
  );
}

/**
 * Everything a volunteer needs in one place: what is coming up for them, their duties (and the open ones they can take),
 * the meetings they are invited to, their tasks, spending requests, and the gate on the day.
 */
export function VolunteerArea({ slug }: { slug: string }) {
  const [tab, setTab] = useState<Id>("home");
  const [fest, setFest] = useState<MyFest | null>(null);
  const [events, setEvents] = useState<FestEvent[]>([]);
  useEffect(() => {
    api<MyFest[]>("/api/fests/mine").then((m) => setFest(m.find((f) => f.slug === slug) ?? null)).catch(() => {});
    api<FestEvent[]>(`/api/fests/${slug}/events`).then(setEvents).catch(() => {});
  }, [slug]);
  useEffect(() => {
    const read = () => { const h = window.location.hash.slice(1); const id = (ITEMS.some((x) => x.id === h) ? h : ALIAS[h]) as Id | undefined; if (id) setTab(id); };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  const go = (id: Id) => { setTab(id); window.history.replaceState(null, "", `#${id}`); };
  return (
    <div>
      <Link href="/dashboard/fests" className="text-sm text-mute hover:text-ink">← Your fests</Link>
      <div className="mb-5 mt-3 flex flex-wrap items-center gap-3"><h1 className="text-[26px] leading-tight">{fest?.name ?? "Your fest"}</h1><Pill tone="neutral">Volunteer</Pill></div>
      <div className="mb-6"><SubTabs label="Your area" items={ITEMS} value={tab} onChange={go} /></div>
      {tab === "home" && <Home slug={slug} go={go} />}
      {tab === "duty" && <ShiftsTab slug={slug} canManage={false} />}
      {tab === "meetings" && <MyMeetings slug={slug} />}
      {tab === "tasks" && <div className="max-w-4xl"><TasksTab slug={slug} canManage={false} mineOnly /></div>}
      {tab === "spend" && <MySpendPanel slug={slug} />}
      {tab === "gate" && <div><p className="mb-4 text-mute">Check people in on the day.</p><GateTab slug={slug} events={events} canUndo={false} /></div>}
    </div>
  );
}
