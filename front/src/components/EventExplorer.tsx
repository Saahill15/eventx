"use client";

import { useEffect, useMemo, useState } from "react";
import { LayoutGrid, List, Search, X } from "lucide-react";
import type { FestEvent } from "@/lib/types";
import { dayKey, formatLongDay, isUpcoming } from "@/lib/format";
import { AnimatedList } from "./AnimatedList";
import { DateStrip } from "./DateStrip";
import { PosterCard } from "./Poster";
import { TicketRow } from "./TicketRow";
import { Chip } from "./ui/Chip";
import { EmptyState } from "./ui/bits";

type View = "list" | "grid";
export interface ExplorerInitial { q?: string; category?: string; date?: string; free?: boolean; view?: string }

export function EventExplorer({ events, initial }: { events: FestEvent[]; initial: ExplorerInitial }) {
  const [q, setQ] = useState(initial.q ?? "");
  const [category, setCategory] = useState<string | null>(initial.category ?? null);
  const [date, setDate] = useState<string | null>(initial.date ?? null);
  const [freeOnly, setFreeOnly] = useState(!!initial.free);
  const [view, setView] = useState<View>(initial.view === "grid" ? "grid" : "list");

  const upcoming = useMemo(() => events.filter(isUpcoming).sort((a, b) => a.date.localeCompare(b.date) || (a.time ?? "").localeCompare(b.time ?? "")), [events]);
  const categories = useMemo(() => Array.from(new Set(upcoming.map((e) => e.category).filter(Boolean) as string[])).sort(), [upcoming]);

  const shown = useMemo(() => {
    const term = q.trim().toLowerCase();
    return upcoming.filter((e) => {
      if (category && e.category !== category) return false;
      if (date && dayKey(e.date) !== date) return false;
      if (freeOnly && !(e.is_free || !e.price)) return false;
      if (!term) return true;
      return [e.title, e.description ?? "", e.location ?? "", e.fest_name ?? "", e.college_name ?? "", e.category ?? ""].some((t) => t.toLowerCase().includes(term));
    });
  }, [upcoming, q, category, date, freeOnly]);

  // Keep the address bar in step with the filters so a filtered view can be shared or reloaded
  useEffect(() => {
    const p = new URLSearchParams();
    if (q.trim()) p.set("q", q.trim());
    if (category) p.set("category", category);
    if (date) p.set("date", date);
    if (freeOnly) p.set("free", "1");
    if (view === "grid") p.set("view", "grid");
    const qs = p.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [q, category, date, freeOnly, view]);

  const active = q.trim() !== "" || category !== null || date !== null || freeOnly;
  const clear = () => { setQ(""); setCategory(null); setDate(null); setFreeOnly(false); };

  return (
    <div>
      <div className="mb-5 flex items-center gap-3">
        <label className="hairline flex h-14 min-w-0 flex-1 items-center gap-3 rounded-full bg-white px-5 shadow-[var(--shadow-soft)] focus-within:ring-4 focus-within:ring-amber/30">
          <Search className="h-5 w-5 text-mute" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search events, venues or fests" aria-label="Search events" className="h-full min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-neutral-400" />
          {q && <button onClick={() => setQ("")} aria-label="Clear search" className="rounded-full p-1 hover:bg-wash"><X className="h-4 w-4" /></button>}
        </label>
        <div className="flex shrink-0 rounded-full bg-wash p-1" role="group" aria-label="View">
          {([["list", List, "List view"], ["grid", LayoutGrid, "Poster view"]] as const).map(([v, Icon, label]) => (
            <button key={v} onClick={() => setView(v)} aria-pressed={view === v} aria-label={label} className={`flex h-10 w-10 items-center justify-center rounded-full transition sm:h-12 sm:w-12 ${view === v ? "bg-white shadow-[var(--shadow-soft)]" : "text-mute"}`}><Icon className="h-5 w-5" /></button>
          ))}
        </div>
      </div>

      <DateStrip value={date} onSelect={setDate} days={21} />

      <div className="no-scrollbar -mx-5 mt-4 flex gap-2 overflow-x-auto px-5 pb-1 sm:-mx-8 sm:px-8" role="group" aria-label="Filters">
        <Chip active={freeOnly} onClick={() => setFreeOnly((v) => !v)}>Free</Chip>
        {categories.map((c) => <Chip key={c} active={category === c} onClick={() => setCategory(category === c ? null : c)}>{c}</Chip>)}
      </div>

      <p className="mb-6 mt-5 text-sm text-mute" aria-live="polite">
        {shown.length} event{shown.length === 1 ? "" : "s"}{date ? ` on ${formatLongDay(date)}` : ""}
        {active && <button onClick={clear} className="ml-3 font-semibold text-ink underline underline-offset-4">Clear filters</button>}
      </p>

      {shown.length === 0 ? (
        <EmptyState title={upcoming.length === 0 ? "No upcoming events yet" : "Nothing matches"} body={upcoming.length === 0 ? "New events show up here as fests publish them." : "Try another day or remove a filter."} />
      ) : view === "list" ? (
        <AnimatedList items={shown} getKey={(e) => e.id} render={(e) => <TicketRow event={e} />} className="space-y-3" />
      ) : (
        <AnimatedList items={shown} getKey={(e) => e.id} render={(e) => <PosterCard event={e} />} className="grid grid-cols-2 gap-4 sm:gap-5 md:grid-cols-3 lg:grid-cols-4" />
      )}
    </div>
  );
}
