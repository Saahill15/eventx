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
import { VolunteerArea } from "./VolunteerArea";
import { ShiftsTab } from "./ShiftsTab";
import { SponsorsTab } from "./SponsorsTab";
import { CompetitionTab } from "./CompetitionTab";
import { FinanceTab } from "./FinanceTab";
import { MeetingsTab } from "./MeetingsTab";
import { ScheduleTab } from "./ScheduleTab";
import { ContingentsTab } from "./ContingentsTab";
import { HandOverCard } from "./HandOverCard";
import { GuidedTour, type TourStep } from "@/components/GuidedTour";
import { SubTabs } from "@/components/ui/SubTabs";
import { CertificatesAdmin, PromoAdmin, WaitlistAdmin } from "./TicketingAdmin";

// The sections of a fest, grouped so the whole set fits on screen: five groups, with the sections of the chosen group shown beneath.
type TabId = "overview" | "details" | "events" | "schedule" | "sponsors" | "announcements" | "registrations" | "gate" | "colleges" | "competition" | "waitlist" | "promos" | "certificates" | "team" | "tasks" | "meetings" | "shifts" | "finance";
const GROUPS: { id: string; label: string; tabs: { id: TabId; label: string }[] }[] = [
  { id: "overview", label: "Overview", tabs: [{ id: "overview", label: "Overview" }] },
  { id: "fest", label: "Your fest", tabs: [{ id: "details", label: "Fest details" }, { id: "events", label: "Events" }, { id: "schedule", label: "Schedule" }, { id: "sponsors", label: "Sponsors" }, { id: "announcements", label: "Announcements" }] },
  { id: "guests", label: "Guests", tabs: [{ id: "registrations", label: "Registrations" }, { id: "waitlist", label: "Waiting lists" }, { id: "promos", label: "Promo codes" }, { id: "certificates", label: "Certificates" }, { id: "gate", label: "Check-in" }, { id: "colleges", label: "Visiting colleges" }, { id: "competition", label: "Competition" }] },
  { id: "team", label: "Team", tabs: [{ id: "team", label: "Committee" }, { id: "tasks", label: "Tasks" }, { id: "meetings", label: "Meetings" }, { id: "shifts", label: "Duty roster" }] },
  { id: "finance", label: "Finance", tabs: [{ id: "finance", label: "Finance" }] },
];
const TABS = GROUPS.flatMap((g) => g.tabs);

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
  // The address says which section is open, on arrival and whenever it changes (a link on the page can change it)
  useEffect(() => {
    const read = () => { const t = window.location.hash.slice(1) as TabId; if (TABS.some((x) => x.id === t)) setTab(t); };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  const [lastIn, setLastIn] = useState<Record<string, string>>({});
  const go = (t: string) => {
    const g = GROUPS.find((x) => x.tabs.some((y) => y.id === t));
    if (g) setLastIn((m) => ({ ...m, [g.id]: t }));
    setTab(t as TabId); window.history.replaceState(null, "", `#${t}`); window.scrollTo({ top: 0 });
  };

  if (role === undefined || (isStaff && !fest)) return <div className="space-y-4"><Skeleton className="h-12 w-72" /><Skeleton className="h-64" /></div>;

  if (role === null) {
    return (
      <div className="mx-auto max-w-md px-6 py-20 text-center">
        <p className="text-mute">Fest not found, or you do not have access to it.</p>
        <Button href="/dashboard/fests" className="mt-6" variant="outline">Back to your fests</Button>
      </div>
    );
  }

  // Volunteers get their own area: what is coming up for them, their duties, meetings, tasks, spending and the gate
  if (!isStaff) return <VolunteerArea slug={slug} />;

  const f = fest!;
  const tour: TourStep[] = [
    { title: "This is your fest's control room", body: "Everything for this fest is in these tabs. Here is what each one is for, in under a minute." },
    { target: "group-overview", title: "Overview", body: "Your fest at a glance, and a checklist of what is left before you can send it for review." },
    { target: "group-fest", title: "Your fest", body: "Fest details (name, dates, banner, logo, contact), your events, the schedule of every day, sponsors and announcements. The number of days is worked out from your dates." },
    { target: "group-guests", title: "Guests", body: "Registrations to approve, check-in on the day, visiting colleges with their entries, accommodation and fees, and the competition between colleges." },
    { target: "group-team", title: "Team", body: "Your committee and its teams, tasks with owners and dates, and meetings with an agenda and minutes." },
    { target: "group-finance", title: "Finance", body: "The budget, requests to spend with approvals, income from sponsors and others, and where the money stands." },
    ...(f.review_status === "draft" || f.review_status === "changes_requested" || f.review_status === "rejected" ? [{ target: "checklist", title: "When this is all ticked", body: "Send the fest to HiveOut for review. After approval, one click makes it live for students." }] : []),
  ];
  const festDays = (() => { const out: string[] = []; if (!f.start_date) return out; const end = f.end_date || f.start_date; for (let d = new Date(`${f.start_date}T00:00:00`); d <= new Date(`${end}T00:00:00`) && out.length < 31; d.setDate(d.getDate() + 1)) out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`); return out; })();
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

      {(() => {
        const group = GROUPS.find((g) => g.tabs.some((t) => t.id === tab)) ?? GROUPS[0];
        const badge = (n: number) => n > 0 && <span className="ml-2 rounded-full bg-brand px-2 py-0.5 text-xs text-on-brand">{n}</span>;
        return (
          <div className="mb-8 space-y-3">
            <nav role="tablist" aria-label="Fest areas" className="no-scrollbar -mx-1 flex gap-2 overflow-x-auto px-1">
              {GROUPS.map((g) => {
                const on = g.id === group.id;
                const remembered = g.tabs.find((t) => t.id === lastIn[g.id]) ?? g.tabs[0];
                return (
                  <button key={g.id} role="tab" data-tour={`group-${g.id}`} aria-selected={on} onClick={() => go(remembered.id)} className={`shrink-0 rounded-full px-5 py-2.5 text-sm font-semibold transition ${on ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)] hover:text-ink"}`}>
                    {g.label}{g.id === "guests" && badge(pending)}
                  </button>
                );
              })}
            </nav>
            {group.tabs.length > 1 && <SubTabs label={`${group.label} sections`} value={tab} onChange={go} items={group.tabs.map((t) => ({ id: t.id, label: t.label, tour: `tab-${t.id}`, badge: t.id === "registrations" ? pending : 0 }))} />}
          </div>
        );
      })()}

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
      {tab === "shifts" && <ShiftsTab slug={slug} canManage festDays={festDays} />}
      {tab === "waitlist" && <WaitlistAdmin slug={slug} />}
      {tab === "promos" && <PromoAdmin slug={slug} />}
      {tab === "certificates" && <CertificatesAdmin slug={slug} />}
      {tab === "finance" && <FinanceTab slug={slug} />}
      {tab === "sponsors" && <SponsorsTab slug={slug} live={f.status === "live"} />}
      {tab === "announcements" && <AnnouncementsTab slug={slug} live={f.status === "live"} events={publicEvents} />}
      {tab === "team" && <div className="max-w-4xl space-y-8"><TeamTab slug={slug} myRole={role} />{role === "owner" && <HandOverCard slug={slug} />}</div>}
    </div>
  );
}
