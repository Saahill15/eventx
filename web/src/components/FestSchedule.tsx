"use client";

import { useMemo, useState } from "react";
import type { FestEvent } from "@/lib/types";
import { dayKey, formatDay, formatLongDay } from "@/lib/format";
import { EventCard } from "./EventCard";
import { Chip } from "./FestBrowser";
import { EmptyState } from "./ui/bits";

export function FestSchedule({ events }: { events: FestEvent[] }) {
  const [category, setCategory] = useState<string | null>(null);
  const [day, setDay] = useState<string | null>(null);

  const sorted = useMemo(() => [...events].sort((a, b) => a.date.localeCompare(b.date) || (a.time ?? "").localeCompare(b.time ?? "")), [events]);
  const days = useMemo(() => Array.from(new Set(sorted.map((e) => dayKey(e.date)))), [sorted]);
  const categories = useMemo(() => Array.from(new Set(sorted.map((e) => e.category).filter(Boolean) as string[])).sort(), [sorted]);

  const shown = sorted.filter((e) => (!category || e.category === category) && (!day || dayKey(e.date) === day));
  const groups = Array.from(new Set(shown.map((e) => dayKey(e.date))));

  if (events.length === 0) return <EmptyState title="No events published yet" body="The committee has not added events. Check back soon." />;

  return (
    <div>
      {days.length > 1 && (
        <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Filter by day">
          <Chip active={day === null} onClick={() => setDay(null)}>All days</Chip>
          {days.map((d) => <Chip key={d} active={day === d} onClick={() => setDay(day === d ? null : d)}>{formatDay(d)}</Chip>)}
        </div>
      )}
      {categories.length > 1 && (
        <div className="mb-8 flex flex-wrap gap-2" role="group" aria-label="Filter by category">
          {categories.map((c) => <Chip key={c} active={category === c} onClick={() => setCategory(category === c ? null : c)}>{c}</Chip>)}
        </div>
      )}
      {shown.length === 0 ? (
        <EmptyState title="Nothing matches" body="Try another day or category." />
      ) : (
        <div className="space-y-10">
          {groups.map((g) => (
            <div key={g}>
              <h3 className="mb-4 font-display text-lg font-extrabold tracking-tight text-neutral-700">{formatLongDay(g)}</h3>
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {shown.filter((e) => dayKey(e.date) === g).map((e) => <EventCard key={e.id} event={e} />)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
