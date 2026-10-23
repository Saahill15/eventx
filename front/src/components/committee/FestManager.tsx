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
import { HandOverCard } from "./HandOverCard";

const TABS = [
  { id: "overview", label: "Overview", staff: true }, { id: "details", label: "Fest details", staff: true }, { id: "events", label: "Events", staff: true },
  { id: "registrations", label: "Registrations", staff: true }, { id: "gate", label: "Check-in", staff: false }, { id: "announcements", label: "Announcements", staff: true }, { id: "team", label: "Committee", staff: true },
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
        <GateTab slug={slug} events={publicEvents} canUndo={false} />
      </div>
    );
  }

  const f = fest!;
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
        </div>
      </div>

      {role === "admin" && <div className="mb-5"><Notice tone="info">You are viewing this fest as an admin.</Notice></div>}

      <nav role="tablist" aria-label="Fest sections" className="no-scrollbar -mx-1 mb-8 flex gap-2 overflow-x-auto px-1">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => go(t.id)} className={`shrink-0 rounded-full px-5 py-2.5 text-sm font-semibold transition ${tab === t.id ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)] hover:text-ink"}`}>
            {t.label}{t.id === "registrations" && pending > 0 && <span className="ml-2 rounded-full bg-brand px-2 py-0.5 text-xs text-on-brand">{pending}</span>}
          </button>
        ))}
      </nav>

      {tab === "overview" && <FestOverviewTab fest={f} role={role} reload={loadFest} goTo={go} />}
      {tab === "details" && <FestDetailsTab key={f.review_status + f.name} fest={f} frozen={frozen} onSaved={loadFest} />}
      {tab === "events" && <EventsTab fest={f} events={events} frozen={frozen} reload={() => { loadEvents(); loadFest(); }} />}
      {tab === "registrations" && <RegistrationsTab events={events} reload={loadEvents} />}
      {tab === "gate" && <GateTab slug={slug} events={publicEvents} canUndo />}
      {tab === "announcements" && <AnnouncementsTab slug={slug} live={f.status === "live"} events={publicEvents} />}
      {tab === "team" && <div className="max-w-4xl space-y-8"><TeamTab slug={slug} myRole={role} />{role === "owner" && <HandOverCard slug={slug} />}</div>}
    </div>
  );
}
