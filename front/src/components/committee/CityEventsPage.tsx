"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import type { FestEvent } from "@/lib/types";
import { formatDay, priceLabel } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Notice, Pill, Skeleton } from "@/components/ui/bits";
import { EventForm } from "./EventForm";

const STATUS = { pending: { label: "Waiting for HiveOut", tone: "amber" }, approved: { label: "Live", tone: "green" }, rejected: { label: "Not approved", tone: "red" } } as const;

/** Standalone events that are not part of a fest. Each one is reviewed by HiveOut before it appears on the site. */
export function CityEventsPage() {
  const [events, setEvents] = useState<FestEvent[] | null>(null);
  const [editing, setEditing] = useState<FestEvent | "new" | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { api<FestEvent[]>("/api/events/mine").then(setEvents).catch((e) => { setError(e instanceof Error ? e.message : "Could not load."); setEvents([]); }); }, []);
  useEffect(load, [load]);

  const act = async (fn: () => Promise<unknown>) => { setBusy(true); setError(""); try { await fn(); load(); } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); } setBusy(false); };

  if (editing) return <EventForm kind="city" event={editing === "new" ? null : editing} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />;

  return (
    <div className="max-w-4xl">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Notice tone="info">Any change to a city event sends it back to HiveOut for review, and it stays hidden until they approve it.</Notice>
        <Button size="sm" onClick={() => setEditing("new")}><Plus className="h-4 w-4" /> New city event</Button>
      </div>
      <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>
      {events === null ? <Skeleton className="h-32" /> : events.length === 0 ? (
        <EmptyState title="No city events yet" body="Create a standalone event such as a concert or a workshop. HiveOut reviews it before it goes live." action={<Button onClick={() => setEditing("new")}>Create a city event</Button>} />
      ) : (
        <div className="space-y-3">
          {events.map((e) => {
            const st = STATUS[e.status];
            return (
              <div key={e.id} className="card p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2 font-semibold">{e.title}<Pill tone={st.tone}>{st.label}</Pill>{e.cancelled && <Pill tone="red">Cancelled</Pill>}</p>
                    <p className="mt-0.5 text-sm text-mute">{formatDay(e.date)}{e.location ? ` · ${e.location}` : ""} · {priceLabel(e)}</p>
                    {e.status === "rejected" && e.reject_reason && <p className="mt-2 text-sm text-neutral-700"><span className="font-semibold">HiveOut said:</span> {e.reject_reason}</p>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {e.status === "approved" && <Button href={`/events/${e.id}`} variant="ghost" size="sm">View</Button>}
                    <Button size="sm" variant="outline" onClick={() => setEditing(e)}>{e.status === "rejected" ? "Fix and resubmit" : "Edit"}</Button>
                    {e.status === "approved" && !e.cancelled && <Button size="sm" variant="outline" disabled={busy} onClick={() => window.confirm(`Cancel "${e.title}"?`) && act(() => api(`/api/events/${e.id}/cancel`, { method: "POST", body: {} }))}>Cancel</Button>}
                    {e.cancelled && <Button size="sm" variant="outline" disabled={busy} onClick={() => act(() => api(`/api/events/${e.id}/restore`, { method: "POST" }))}>Restore</Button>}
                    <button disabled={busy} onClick={() => window.confirm(`Delete "${e.title}"?`) && act(() => api(`/api/events/${e.id}`, { method: "DELETE" }))} className="px-2 text-sm font-semibold text-red-600 hover:underline">Delete</button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
