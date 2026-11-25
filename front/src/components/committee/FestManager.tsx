"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FestEvent, FestManage, ManagedEvent, MyFest } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Notice, Pill, Skeleton } from "@/components/ui/bits";
import { AnnouncementsTab } from "./AnnouncementsTab";
import { ReviewPill, useMyFests } from "./CommitteeShell";
import { EventsTab } from "./EventsTab";
import { FestDetailsTab } from "./FestDetailsTab";
import { FestOverviewTab } from "./FestOverviewTab";
import { GateTab } from "./GateTab";
import { RegistrationsTab } from "./RegistrationsTab";
import { TeamTab } from "./TeamTab";
import { TasksTab } from "./TasksTab";
import { MyTeamPanel } from "./MyTeamPanel";
import { SponsorsTab } from "./SponsorsTab";
import { CompetitionTab } from "./CompetitionTab";
import { MeetingsTab } from "./MeetingsTab";
import { ScheduleTab } from "./ScheduleTab";
import { ContingentsTab } from "./ContingentsTab";
import { HandOverCard } from "./HandOverCard";
import { GuidedTour, type TourStep } from "@/components/GuidedTour";

const TABS = [
  { id: "overview", label: "Overview", staff: true }, { id: "details", label: "Fest details", staff: true }, { id: "events", label: "Events", staff: true }, { id: "schedule", label: "Schedule", staff: true },
  { id: "registrations", label: "Registrations", staff: true }, { id: "colleges", label: "Visiting colleges", staff: true }, { id: "competition", label: "Competition", staff: true }, { id: "tasks", label: "Tasks", staff: true }, { id: "meetings", label: "Meetings", staff: true }, { id: "gate", label: "Check-in", staff: false }, { id: "sponsors", label: "Sponsors", staff: true }, { id: "announcements", label: "Announcements", staff: true }, { id: "team", label: "Committee", staff: true },
] as const;
type TabId = (typeof TABS)[number]["id"];

export function FestManager({ slug }: { slug: string }) {
  const { reload: reloadSidebar } = useMyFests();
  const [fest, setFest] = useState<FestManage | null>(null);
  const [role, setRole] = useState<MyFest["my_role"] | null | undefined>(undefined);
  const [events, setEvents] = useState<ManagedEvent[]>([]);
  const [publicEvents, setPublicEvents] = useState<FestEvent[]>([]);
  const [tab, setTab] = useState<TabId>("overview");

  const isStaff = role === "owner" || role === "core" || role === "admin";

  // A short tour of this page: once, the first time an organiser opens a fest, and again whenever they ask (?tour=1 or the button)
  const [touring, setTouring] = useState(false);
  const FEST_TOUR_KEY = "hiveout:tour:fest:v1";
  const endTour = () => { setTouring(false); try { window.localStorage.setItem(FEST_TOUR_KEY, "1"); } catch { /* storage blocked */ } if (window.location.search.includes("tour=")) window.history.replaceState(null, "", window.location.pathname + window.location.hash); };

  const loadFest = useCallback(async () => {
    setFest(await api<FestManage>(`/api/fests/${slug}/manage`));
    reloadSidebar();
  }, [slug, reloadSidebar]);
  const loadEvents = useCallback(async () => {
    api<ManagedEvent[]>(`/api/fests/${slug}/manage/events`).then(setEvents).catch(() => {});
  }, [slug]);

  useEffect(() => {
    api<MyFest[]>("/api/fests/mine").then((mine) => setRole(mine.find((f) => f.slug === slug)?.my_role ?? null)).catch(() => setRole(null));
  }, [slug]);
  useEffect(() => {
    if (!isStaff) return;
    loadFest().catch(() => setRole(null));
    loadEvents();
  }, [isStaff, loadFest, loadEvents]);
  useEffect(() => { if (role) api<FestEvent[]>(`/api/fests/${slug}/events`).then(setPublicEvents).catch(() => {}); }, [role, slug, events]);
  useEffect(() => {
    if (!isStaff || !fest || role === "admin") return;
    let seen = false;
    try { seen = !!window.localStorage.getItem(FEST_TOUR_KEY); } catch { /* storage blocked: do not nag */ seen = true; }
    if (new URLSearchParams(window.location.search).get("tour") === "1" || !seen) { const t = window.setTimeout(() => setTouring(true), 700); return () => window.clearTimeout(t); }
  }, [isStaff, fest, role]);
  useEffect(() => {
    const t = window.location.hash.slice(1) as TabId;
    if (TABS.some((x) => x.id === t)) setTab(t);
  }, []);
  const go = (t: string) => { setTab(t as TabId); window.history.replaceState(null, "", `#${t}`); window.scrollTo({ top: 0 }); };

  if (role === undefined || (isStaff && !fest)) return <div className="space-y-4"><Skeleton className="h-12 w-72" /><Skeleton className="h-64" /></div>;

  if (role === null) {
    return (
      <div className="mx-auto max-w-md px-6 py-20 text-center">
        <p className="text-mute">Fest not found, or you do not have access to it.</p>
        <Button href="/dashboard/fests" className="mt-6" variant="outline">Back to your fests</Button>
      </div>
    );
  }

  // Volunteers help on the day: they only get the check-in screen
  if (!isStaff) {
    return (
      <div>
        <Link href="/dashboard/fests" className="text-sm text-mute hover:text-ink">← Your fests</Link>
        <h1 className="mb-2 mt-3 text-[26px] leading-tight">Check-in</h1>
        <p className="mb-6 text-mute">You are a volunteer on this fest. You can check people in on the day.</p>
        <MyTeamPanel slug={slug} />
        <div className="mb-8"><TasksTab slug={slug} canManage={false} mineOnly /></div>
        <GateTab slug={slug} events={publicEvents} canUndo={false} />
      </div>
    );
  }

  const f = fest!;
  const tour: TourStep[] = [
    { title: "This is your fest's control room", body: "Everything for this fest is in these tabs. Here is what each one is for, in under a minute." },
    { target: "tab-overview", title: "Overview", body: "Your fest at a glance, and a checklist of what is left before you can send it for review." },
    { target: "tab-details", title: "Fest details", body: "The name, dates, banner and logo, where it is, and who HiveOut can contact. The number of days is worked out from your dates." },
    { target: "tab-events", title: "Events", body: "Add your events from a template. Choose which day or days each one runs, whether people register, and team sizes." },
    { target: "tab-schedule", title: "Schedule", body: "Every day of your fest, with each event in its place. If two events want the same venue at the same time, it tells you." },
    { target: "tab-tasks", title: "Tasks, meetings and committee", body: "Keep your team organised: give out tasks, run meetings with an agenda and minutes, and set up your teams and who reports to whom." },
    { target: "tab-colleges", title: "Visiting colleges", body: "If other colleges take part, switch this on to let their leaders register their teams. Leave it off if your fest is just for your own college." },
    ...(f.review_status === "draft" || f.review_status === "changes_requested" || f.review_status === "rejected" ? [{ target: "checklist", title: "When this is all ticked", body: "Send the fest to HiveOut for review. After approval, one click makes it live for students." }] : []),
  ];
  const frozen = f.review_status === "in_review" && role !== "admin";
  const pending = events.reduce((n, e) => n + e.pending_count, 0);

  return (
    <div>
      <Link href="/dashboard/fests" className="text-sm text-mute hover:text-ink">← Your fests</Link>
      <div className="mb-6 mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[26px] leading-tight">{f.name}</h1>
            <Pill tone={f.status === "live" ? "green" : "neutral"}>{f.status === "live" ? "Live" : "Not live"}</Pill>
            <ReviewPill status={f.review_status} />
          </div>
          {f.status === "live" && <Link href={`/fests/${f.slug}`} className="mt-1 inline-block text-sm font-semibold hover:underline">View public page →</Link>}
          {role !== "admin" && <button onClick={() => setTouring(true)} className="mt-1 block text-sm font-semibold text-mute underline underline-offset-4 hover:text-ink">Take a tour of this page</button>}
        </div>
      </div>

      {role === "admin" && <div className="mb-5"><Notice tone="info">You are viewing this fest as an admin.</Notice></div>}

      <nav role="tablist" aria-label="Fest sections" className="no-scrollbar -mx-1 mb-8 flex gap-2 overflow-x-auto px-1">
        {TABS.map((t) => (
          <button key={t.id} role="tab" data-tour={`tab-${t.id}`} aria-selected={tab === t.id} onClick={() => go(t.id)} className={`shrink-0 rounded-full px-5 py-2.5 text-sm font-semibold transition ${tab === t.id ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)] hover:text-ink"}`}>
            {t.label}{t.id === "registrations" && pending > 0 && <span className="ml-2 rounded-full bg-brand px-2 py-0.5 text-xs text-on-brand">{pending}</span>}
          </button>
        ))}
      </nav>

      {touring && <GuidedTour steps={tour} onClose={() => endTour()} />}
      {tab === "overview" && <FestOverviewTab fest={f} role={role} reload={loadFest} goTo={go} />}
      {tab === "details" && <FestDetailsTab key={f.review_status + f.name} fest={f} frozen={frozen} onSaved={loadFest} />}
      {tab === "events" && <EventsTab fest={f} events={events} frozen={frozen} goTo={go} reload={() => { loadEvents(); loadFest(); }} />}
      {tab === "registrations" && <RegistrationsTab events={events} reload={loadEvents} />}
      {tab === "colleges" && <ContingentsTab slug={slug} />}
      {tab === "competition" && <CompetitionTab slug={slug} goTo={go} />}
      {tab === "schedule" && <ScheduleTab slug={slug} goTo={go} />}
      {tab === "tasks" && <TasksTab slug={slug} canManage />}
      {tab === "meetings" && <MeetingsTab slug={slug} />}
      {tab === "gate" && <GateTab slug={slug} events={publicEvents} canUndo />}
      {tab === "sponsors" && <SponsorsTab slug={slug} live={f.status === "live"} />}
      {tab === "announcements" && <AnnouncementsTab slug={slug} live={f.status === "live"} events={publicEvents} />}
      {tab === "team" && <div className="max-w-4xl space-y-8"><TeamTab slug={slug} myRole={role} />{role === "owner" && <HandOverCard slug={slug} />}</div>}
    </div>
  );
}
