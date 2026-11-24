"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Schedule, ScheduleItem } from "@/lib/types";
import { formatDay, formatTime } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Notice, Pill, Skeleton } from "@/components/ui/bits";

const range = (e: ScheduleItem) => e.time ? `${formatTime(e.time)}${e.end_time ? `–${formatTime(e.end_time)}` : ""}` : "No time yet";
const NO_VENUE = "No venue yet";

/** Every event by day and venue, so the committee can see the whole fest at once and spot two events wanting the same room. */
export function ScheduleTab({ slug, goTo }: { slug: string; goTo: (tab: string) => void }) {
  const [data, setData] = useState<Schedule | null>(null);
  const [day, setDay] = useState<string>("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<Schedule>(`/api/fests/${slug}/schedule`).then((s) => { setData(s); setDay((d) => d || s.days[0]?.date || ""); }).catch((e) => { setError(e instanceof Error ? e.message : "Could not load the schedule."); setData({ days: [], venues: [], clashes: [], unscheduled: [] }); });
  }, [slug]);

  const byId = useMemo(() => new Map((data?.days ?? []).flatMap((d) => d.items).map((i) => [i.id, i])), [data]);
  if (data === null) return <Skeleton className="h-48" />;
  if (data.days.length === 0) return <div className="max-w-3xl space-y-4"><ErrorNote>{error}</ErrorNote><EmptyState title="Nothing scheduled yet" body="Add events with a date, time and venue, and the whole fest shows up here, day by day." action={<Button onClick={() => goTo("events")}>Add events</Button>} /></div>;

  const current = data.days.find((d) => d.date === day) ?? data.days[0];
  // One column per venue, however it was capitalised or spaced: the server treats "Lab 2" and "lab  2" as the same place
  const venueOf = (i: ScheduleItem) => (i.location ?? "").trim().replace(/\s+/g, " ") || NO_VENUE;
  const spellings = new Map<string, string>();
  for (const i of current.items) if (!spellings.has(venueOf(i).toLowerCase())) spellings.set(venueOf(i).toLowerCase(), venueOf(i));
  const venues = Array.from(spellings.values());
  const same = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();

  return (
    <div className="space-y-5">
      {data.clashes.length > 0 && (
        <Notice tone="warn">
          <strong>{data.clashes.length} clash{data.clashes.length === 1 ? "" : "es"} to sort out.</strong>
          <ul className="mt-1.5 space-y-1">{data.clashes.map((c) => <li key={`${c.first_id}-${c.second_id}`}>{formatDay(c.date)} at {c.venue}: &ldquo;{byId.get(c.first_id)?.title}&rdquo; and &ldquo;{byId.get(c.second_id)?.title}&rdquo; overlap.</li>)}</ul>
        </Notice>
      )}
      {data.unscheduled.length > 0 && (
        <Notice tone="info">
          <strong>{data.unscheduled.length} event{data.unscheduled.length === 1 ? " has" : "s have"} no time or venue yet:</strong> {data.unscheduled.map((e) => e.title).join(", ")}. <button onClick={() => goTo("events")} className="font-semibold underline underline-offset-4">Edit events</button>
        </Notice>
      )}

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Days">
        {data.days.map((d) => (
          <button key={d.date} role="tab" aria-selected={d.date === current.date} onClick={() => setDay(d.date)} className={`rounded-full px-4 py-2 text-sm font-semibold transition ${d.date === current.date ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)] hover:text-ink"}`}>
            {formatDay(d.date)} <span className="font-normal opacity-70">({d.items.length})</span>{d.items.some((i) => i.clash_ids.length > 0) ? <span className="ml-1.5 text-red-500" aria-label="has a clash">●</span> : null}
          </button>
        ))}
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(15rem, 1fr))" }}>
        {venues.map((v) => (
          <section key={v} aria-label={v} className="space-y-3 rounded-3xl bg-wash p-3">
            <h3 className="px-2 pt-1 text-sm font-semibold">{v}</h3>
            {current.items.filter((i) => same(venueOf(i), v)).map((e) => (
              <div key={e.id} className={`rounded-2xl bg-white p-4 shadow-[var(--shadow-card)] ${e.clash_ids.length ? "ring-2 ring-red-400" : ""} ${e.cancelled ? "opacity-60" : ""}`}>
                <p className="text-xs font-semibold text-mute">{range(e)}</p>
                <p className="mt-0.5 font-semibold">{e.title}</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">{e.category && <Pill tone="neutral">{e.category}</Pill>}{e.cancelled && <Pill tone="red">Cancelled</Pill>}</div>
                {e.clash_ids.length > 0 && <p className="mt-2 text-xs font-semibold text-red-600">Clashes with {e.clash_ids.map((id) => byId.get(id)?.title).filter(Boolean).join(", ")}</p>}
              </div>
            ))}
          </section>
        ))}
      </div>
    </div>
  );
}
