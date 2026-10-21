"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Fest, ManagedEvent, MyFest } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Pill, Skeleton } from "@/components/ui/bits";
import { Notice } from "@/components/ui/bits";
import { EventsTab } from "./EventsTab";
import { FestSettingsTab } from "./FestSettingsTab";
import { RegistrationsTab } from "./RegistrationsTab";
import { TeamTab } from "./TeamTab";

const TABS = [
  { id: "events", label: "Events" },
  { id: "registrations", label: "Registrations" },
  { id: "team", label: "Team" },
  { id: "page", label: "Fest page" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export function FestManager({ slug }: { slug: string }) {
  const [fest, setFest] = useState<Fest | null>(null);
  const [role, setRole] = useState<MyFest["my_role"] | null | undefined>(undefined);
  const [events, setEvents] = useState<ManagedEvent[]>([]);
  const [tab, setTab] = useState<TabId>("events");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const loadFest = useCallback(() => api<Fest>(`/api/fests/${slug}`).then(setFest), [slug]);
  const loadEvents = useCallback(() => api<ManagedEvent[]>(`/api/fests/${slug}/manage/events`).then(setEvents).catch((e) => setError(e instanceof Error ? e.message : "Could not load events.")), [slug]);

  useEffect(() => {
    Promise.all([api<MyFest[]>("/api/fests/mine"), loadFest()])
      .then(([mine]) => setRole(mine.find((f) => f.slug === slug)?.my_role ?? null))
      .catch(() => setRole(null));
  }, [slug, loadFest]);

  const isStaff = role === "owner" || role === "core" || role === "admin";
  useEffect(() => { if (isStaff) loadEvents(); }, [isStaff, loadEvents]);

  const toggleLive = async () => {
    if (!fest) return;
    setBusy(true); setError("");
    try { await api(`/api/fests/${slug}/status`, { method: "PATCH", body: { status: fest.status === "live" ? "draft" : "live" } }); await loadFest(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not change the fest status."); }
    finally { setBusy(false); }
  };

  if (role === undefined) return <div className="mx-auto max-w-7xl space-y-4 px-6 py-8"><Skeleton className="h-12 w-72" /><Skeleton className="h-64" /></div>;

  if (!fest || role === null) {
    return (
      <div className="mx-auto max-w-md px-6 py-20 text-center">
        <p className="text-neutral-500">Fest not found, or you do not have access to it.</p>
        <Button href="/committee" className="mt-6" variant="outline">Back to your fests</Button>
      </div>
    );
  }
  if (!isStaff) {
    return (
      <div className="mx-auto max-w-md px-6 py-20 text-center">
        <h1 className="font-display text-2xl font-extrabold tracking-tight">{fest.name}</h1>
        <p className="mb-6 mt-2 text-neutral-500">You are a volunteer on this fest. Management tools are for the director and core team.</p>
        <Button href={`/fest/${fest.slug}`}>View the fest page</Button>
      </div>
    );
  }

  const pending = events.reduce((n, e) => n + e.pending_count, 0);

  return (
    <div className="mx-auto max-w-7xl px-6 pb-8 pt-6">
      <Link href="/committee" className="text-sm text-neutral-500 hover:text-ink">← Your fests</Link>
      <div className="mb-6 mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">{fest.name}</h1>
            <Pill tone={fest.status === "live" ? "green" : "neutral"}>{fest.status === "live" ? "Live" : "Draft"}</Pill>
          </div>
          <Link href={`/fest/${fest.slug}`} className="mt-1 inline-block text-sm font-semibold text-amber-ink hover:underline">View public page →</Link>
        </div>
        <Button variant={fest.status === "live" ? "outline" : "amber"} onClick={toggleLive} disabled={busy}>
          {busy ? "Updating…" : fest.status === "live" ? "Take offline" : "Make fest live"}
        </Button>
      </div>

      {fest.status !== "live" && <div className="mb-6"><Notice tone="warn">This fest is a draft. Only your team can see it, and students cannot get passes yet. Make it live when you are ready.</Notice></div>}
      <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>

      <div className="bg-white ring-1 ring-black/5 shadow-[var(--shadow-soft)] no-scrollbar mb-8 inline-flex max-w-full gap-1 overflow-x-auto rounded-full p-1.5" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
            className={`relative whitespace-nowrap rounded-full px-4 py-2 text-sm font-semibold transition-colors ${tab === t.id ? "text-white" : "text-neutral-600 hover:bg-black/5"}`}>
            {tab === t.id && <motion.span layoutId="manager-tab" className="absolute inset-0 rounded-full bg-ink" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
            <span className="relative">{t.label}</span>
            {t.id === "registrations" && pending > 0 && <span className="relative ml-2 rounded-full bg-amber px-2 py-0.5 text-xs text-ink">{pending}</span>}
          </button>
        ))}
      </div>

      {tab === "events" && <EventsTab fest={fest} events={events} reload={loadEvents} />}
      {tab === "registrations" && <RegistrationsTab events={events} reload={loadEvents} />}
      {tab === "team" && <TeamTab slug={slug} myRole={role} />}
      {tab === "page" && <FestSettingsTab fest={fest} onSaved={loadFest} />}
    </div>
  );
}
