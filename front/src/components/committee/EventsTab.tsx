"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import type { FestManage, ManagedEvent } from "@/lib/types";
import { formatDay, formatTime, priceLabel } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Notice, Pill } from "@/components/ui/bits";
import { EventForm } from "./EventForm";

export function EventsTab({ fest, events, frozen, reload }: { fest: FestManage; events: ManagedEvent[]; frozen: boolean; reload: () => void }) {
  const [editing, setEditing] = useState<ManagedEvent | "new" | null>(null);
  const [cancelling, setCancelling] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); setCancelling(null); setReason(""); reload(); } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); }
    setBusy(false);
  };

  if (editing) return <EventForm kind="fest" fest={fest} event={editing === "new" ? null : editing} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); reload(); }} />;

  return (
    <div className="max-w-4xl">
      {frozen && <div className="mb-5"><Notice tone="warn">This fest is with HiveOut for review, so events are locked. Withdraw it from the Overview tab to make changes.</Notice></div>}
      <div className="mb-5 flex items-center justify-between">
        <p className="text-sm text-mute">{events.length} event{events.length === 1 ? "" : "s"}</p>
        {!frozen && <Button size="sm" onClick={() => setEditing("new")}><Plus className="h-4 w-4" /> New event</Button>}
      </div>
      <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>
      {events.length === 0 ? (
        <EmptyState title="No events yet" body="Add the events of your fest. Every fest needs at least one before it can be reviewed." action={!frozen ? <Button onClick={() => setEditing("new")}>Add an event</Button> : undefined} />
      ) : (
        <div className="space-y-3">
          {events.map((e) => (
            <div key={e.id} className={`card p-5 ${e.cancelled ? "opacity-70" : ""}`}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2 font-semibold">{e.title}{e.cancelled && <Pill tone="red">Cancelled</Pill>}{e.students_only && <Pill tone="neutral">Students only</Pill>}</p>
                  <p className="mt-0.5 text-sm text-mute">{formatDay(e.date)}{e.time ? ` · ${formatTime(e.time)}${e.end_time ? `–${formatTime(e.end_time)}` : ""}` : ""}{e.location ? ` · ${e.location}` : ""} · {priceLabel(e)}</p>
                  <p className="mt-1 text-sm text-neutral-700">{e.requires_registration ? `${e.registration_count}${e.registration_limit ? ` / ${e.registration_limit}` : ""} registered${e.pending_count ? ` · ${e.pending_count} waiting` : ""}` : "No registration needed"}</p>
                  {e.cancelled && e.cancel_reason && <p className="mt-1 text-sm text-mute">Reason: {e.cancel_reason}</p>}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button href={`/events/${e.id}`} variant="ghost" size="sm">View</Button>
                  {!frozen && !e.cancelled && <Button variant="outline" size="sm" onClick={() => setEditing(e)}>Edit</Button>}
                  {!frozen && !e.cancelled && <Button variant="outline" size="sm" onClick={() => { setCancelling(e.id); setReason(""); }}>Cancel event</Button>}
                  {e.cancelled && <Button variant="outline" size="sm" disabled={busy} onClick={() => act(() => api(`/api/events/${e.id}/restore`, { method: "POST" }))}>Restore</Button>}
                  {!frozen && e.registration_count === 0 && <button disabled={busy} onClick={() => window.confirm(`Delete "${e.title}"? This cannot be undone.`) && act(() => api(`/api/events/${e.id}`, { method: "DELETE" }))} className="px-2 text-sm font-semibold text-red-600 hover:underline">Delete</button>}
                </div>
              </div>
              {cancelling === e.id && (
                <div className="mt-4 space-y-3 rounded-2xl bg-wash p-4">
                  <p className="text-sm">Everyone registered will be told. {e.registration_count === 0 && "Nobody has registered, so you could delete it instead."}</p>
                  <input className="field" placeholder="Reason (shown to students)" maxLength={500} value={reason} onChange={(ev) => setReason(ev.target.value)} />
                  <div className="flex gap-2"><Button size="sm" disabled={busy} onClick={() => act(() => api(`/api/events/${e.id}/cancel`, { method: "POST", body: { reason: reason.trim() || null } }))}>Cancel the event</Button><Button size="sm" variant="ghost" onClick={() => setCancelling(null)}>Keep it</Button></div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
