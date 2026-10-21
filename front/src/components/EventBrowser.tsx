"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { FestEvent } from "@/lib/types";
import { isThisWeek, isUpcoming } from "@/lib/format";
import { AnimatedGrid } from "./AnimatedGrid";
import { EventCard } from "./EventCard";
import { Chip } from "./FestBrowser";
import { EmptyState } from "./ui/bits";

type When = "all" | "week";

export function EventBrowser({ events, initial }: { events: FestEvent[]; initial: { q?: string; category?: string; when?: string; free?: boolean } }) {
  const [q, setQ] = useState(initial.q ?? "");
  const [category, setCategory] = useState<string | null>(initial.category ?? null);
  const [when, setWhen] = useState<When>(initial.when === "week" ? "week" : "all");
  const [freeOnly, setFreeOnly] = useState(!!initial.free);

  const upcoming = useMemo(() => events.filter(isUpcoming).sort((a, b) => a.date.localeCompare(b.date)), [events]);
  const categories = useMemo(() => Array.from(new Set(upcoming.map((e) => e.category).filter(Boolean) as string[])).sort(), [upcoming]);

  const shown = useMemo(() => {
    const term = q.trim().toLowerCase();
    return upcoming.filter((e) => {
      if (category && e.category !== category) return false;
      if (when === "week" && !isThisWeek(e)) return false;
      if (freeOnly && !(e.is_free || !e.price)) return false;
      if (!term) return true;
      return [e.title, e.description ?? "", e.location ?? "", e.fest_name ?? "", e.college_name ?? "", e.category ?? ""].some((t) => t.toLowerCase().includes(term));
    });
  }, [upcoming, q, category, when, freeOnly]);

  // Keep the address bar in step with the filters so a filtered view can be shared or reloaded
  useEffect(() => {
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    if (category) params.set("category", category);
    if (when === "week") params.set("when", "week");
    if (freeOnly) params.set("free", "1");
    const qs = params.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [q, category, when, freeOnly]);

  const filtered = q.trim() !== "" || category !== null || when !== "all" || freeOnly;
  const reset = () => { setQ(""); setCategory(null); setWhen("all"); setFreeOnly(false); };

  return (
    <>
      <div className="glass-strong mb-5 flex h-14 items-center gap-3 rounded-full pl-5 pr-4">
        <Search className="h-5 w-5 text-neutral-400" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search events, venues or fests" aria-label="Search events" className="h-full flex-1 bg-transparent outline-none placeholder:text-neutral-400" />
      </div>
      <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Filters">
        <Chip active={when === "week"} onClick={() => setWhen(when === "week" ? "all" : "week")}>This week</Chip>
        <Chip active={freeOnly} onClick={() => setFreeOnly((v) => !v)}>Free</Chip>
        <span className="mx-1 hidden w-px bg-black/10 sm:block" />
        {categories.map((c) => <Chip key={c} active={category === c} onClick={() => setCategory(category === c ? null : c)}>{c}</Chip>)}
      </div>
      <p className="mb-6 text-sm text-neutral-500" aria-live="polite">
        {shown.length} event{shown.length === 1 ? "" : "s"}
        {filtered && <button onClick={reset} className="ml-3 font-semibold text-hive-ink underline-offset-2 hover:underline">Clear filters</button>}
      </p>
      {shown.length === 0 ? (
        <EmptyState title={upcoming.length === 0 ? "No upcoming events yet" : "No events match"} body={upcoming.length === 0 ? "New events show up here as fests publish them." : "Try removing a filter."} />
      ) : (
        <AnimatedGrid items={shown} getKey={(e) => e.id} render={(e) => <EventCard event={e} />} />
      )}
    </>
  );
}
