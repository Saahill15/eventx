"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Contingent, ContingentSettings, ScoredEvent } from "@/lib/types";
import { Notice, Skeleton } from "@/components/ui/bits";
import { AwardsPanel, SettingsPanel, StandingsPanel } from "./CompetitionBoard";
import { AuctionPanel, MeetsPanel } from "./CompetitionMeets";
import { ResultsPanel, RulesPanel } from "./CompetitionRules";

const SECTIONS = [
  { id: "standings", label: "Standings" }, { id: "meets", label: "CL meets" }, { id: "auction", label: "Name auction" },
  { id: "results", label: "Event results" }, { id: "rules", label: "Rules and penalties" }, { id: "awards", label: "Awards" }, { id: "settings", label: "Settings" },
] as const;
type SectionId = (typeof SECTIONS)[number]["id"];

/**
 * The competition between visiting colleges. Every contingent holds points: it starts with the fest's starting points, earns
 * more at CL meet tasks and in events, spends some on names at the auction, and loses some to penalties. This is where the
 * committee runs all of it.
 */
export function CompetitionTab({ slug, goTo }: { slug: string; goTo?: (tab: "colleges") => void }) {
  const [section, setSection] = useState<SectionId>("standings");
  const [settings, setSettings] = useState<ContingentSettings | null>(null);
  const [people, setPeople] = useState<Contingent[] | null>(null);
  const [events, setEvents] = useState<ScoredEvent[] | null>(null);

  const loadPeople = useCallback(() => { api<Contingent[]>(`/api/fests/${slug}/contingents?status=approved`).then(setPeople).catch(() => setPeople([])); }, [slug]);
  const loadEvents = useCallback(() => { api<ScoredEvent[]>(`/api/fests/${slug}/competition/events`).then(setEvents).catch(() => setEvents([])); }, [slug]);
  useEffect(() => { api<ContingentSettings>(`/api/fests/${slug}/contingents/settings`).then(setSettings).catch(() => {}); loadPeople(); loadEvents(); }, [slug, loadPeople, loadEvents]);

  if (!settings || !people) return <Skeleton className="h-48" />;
  const term = settings.term.toLowerCase();

  return (
    <div className="space-y-6">
      {!settings.enabled && (
        <Notice tone="info">Visiting colleges are switched off for this fest, so nobody can take part yet.{" "}
          {goTo ? <button onClick={() => goTo("colleges")} className="font-semibold underline underline-offset-4">Switch them on</button> : <Link href="#colleges" className="font-semibold underline underline-offset-4">Switch them on</Link>}</Notice>
      )}
      <nav role="tablist" aria-label="Competition sections" className="no-scrollbar -mx-1 flex gap-2 overflow-x-auto px-1">
        {SECTIONS.map((s) => (
          <button key={s.id} role="tab" aria-selected={section === s.id} onClick={() => setSection(s.id)} className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold transition ${section === s.id ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)] hover:text-ink"}`}>{s.label}</button>
        ))}
      </nav>
      <p className="text-[13px] text-mute">{people.length} approved {term}{people.length === 1 ? "" : "s"} taking part.</p>

      {section === "standings" && <StandingsPanel slug={slug} people={people} />}
      {section === "meets" && <MeetsPanel slug={slug} people={people} />}
      {section === "auction" && <AuctionPanel slug={slug} people={people} />}
      {section === "results" && <ResultsPanel slug={slug} people={people} events={events} reload={loadEvents} />}
      {section === "rules" && <RulesPanel slug={slug} people={people} events={events ?? []} reload={loadEvents} />}
      {section === "awards" && <AwardsPanel slug={slug} people={people} events={events ?? []} />}
      {section === "settings" && <SettingsPanel slug={slug} />}
    </div>
  );
}
