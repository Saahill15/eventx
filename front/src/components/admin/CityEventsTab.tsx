"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FestEvent } from "@/lib/types";
import { formatDay, priceLabel } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Skeleton } from "@/components/ui/bits";
import { useAction } from "./shared";

export function CityEventsTab() {
  const [rejecting, setRejecting] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [events, setEvents] = useState<FestEvent[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => { api<FestEvent[]>("/api/admin/events/pending").then(setEvents).catch((e) => { setError(e instanceof Error ? e.message : "Could not load."); setEvents([]); }); }, []);
  useEffect(load, [load]);
  const act = useAction(load);

  return (
    <div>
      <ErrorNote>{error || act.error}</ErrorNote>
      {events === null ? <Skeleton className="h-32" /> : events.length === 0 ? <EmptyState title="No pending events" body="Fest events publish with their fest. Only standalone city events wait for review here." /> : (
        <div className="space-y-3">
          {events.map((e) => (
            <div key={e.id} className="card flex flex-wrap items-center justify-between gap-3 p-5">
              <div className="min-w-0">
                <p className="font-semibold">{e.title}</p>
                <p className="text-sm text-mute">{formatDay(e.date)}{e.location ? ` · ${e.location}` : ""} · {priceLabel(e)}{e.category ? ` · ${e.category}` : ""}</p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" disabled={act.busy} onClick={() => act.run(() => api(`/api/admin/events/${e.id}/approve`, { method: "POST" }))}>Approve</Button>
                <Button size="sm" variant="outline" disabled={act.busy} onClick={() => { setRejecting(rejecting === e.id ? null : e.id); setReason(""); }}>Reject</Button>
              </div>
              {rejecting === e.id && (
                <div className="mt-1 flex w-full flex-wrap gap-2">
                  <input className="field min-w-0 flex-1" placeholder="Why? The organiser will see this." maxLength={500} value={reason} onChange={(ev) => setReason(ev.target.value)} />
                  <Button size="sm" disabled={act.busy || reason.trim().length < 3} onClick={async () => { if (await act.run(() => api(`/api/admin/events/${e.id}/reject`, { method: "POST", body: { reason } }))) setRejecting(null); }}>Send rejection</Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
