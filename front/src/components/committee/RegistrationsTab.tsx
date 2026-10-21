"use client";

import { useCallback, useEffect, useState } from "react";
import { Download } from "lucide-react";
import { api, downloadFile } from "@/lib/api";
import type { ManagedEvent, RegistrationDetail } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Pill, Skeleton } from "@/components/ui/bits";

const tone = { approved: "green", pending: "amber", rejected: "red" } as const;
const label = { approved: "Confirmed", pending: "Waiting", rejected: "Rejected" } as const;

export function RegistrationsTab({ events, reload }: { events: ManagedEvent[]; reload: () => void }) {
  const withReg = events.filter((e) => e.requires_registration);
  const [eventId, setEventId] = useState<number | null>(withReg[0]?.id ?? null);
  const [rows, setRows] = useState<RegistrationDetail[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async (id: number) => {
    try { setRows(await api<RegistrationDetail[]>(`/api/fest-events/${id}/registrations`)); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load registrations."); setRows([]); }
  }, []);

  useEffect(() => { if (eventId) { setRows(null); load(eventId); } }, [eventId, load]);

  const decide = async (id: number, approve: boolean) => {
    setError("");
    try { await api(`/api/fest-events/registrations/${id}/${approve ? "approve" : "reject"}`, { method: "POST" }); reload(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not update that registration."); }
    if (eventId) load(eventId);
  };

  const exportCsv = async () => {
    setError("");
    try { await downloadFile(`/api/fest-events/${eventId}/registrations.csv`, `registrations-event-${eventId}.csv`); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not download the file."); }
  };

  if (withReg.length === 0) {
    return <EmptyState title="No events take registrations yet" body='Turn on "Students must register" when you add or edit an event.' />;
  }

  const count = (s: string) => rows?.filter((r) => r.approval_status === s).length ?? 0;

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end gap-3">
        <label className="min-w-[220px] flex-1">
          <span className="mb-1.5 block text-sm font-medium">Event</span>
          <select className="field" value={eventId ?? ""} onChange={(e) => setEventId(Number(e.target.value))}>
            {withReg.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
          </select>
        </label>
        <Button variant="outline" onClick={exportCsv} disabled={!rows || rows.length === 0}><Download className="h-4 w-4" /> Download CSV</Button>
      </div>
      <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>
      {rows && <p className="mb-4 text-sm text-neutral-500">{rows.length} total · {count("approved")} confirmed · {count("pending")} waiting · {count("rejected")} rejected</p>}

      {rows === null ? <Skeleton className="h-24" /> : rows.length === 0 ? (
        <EmptyState title="Nobody has registered yet" body="Registrations appear here as students sign up." />
      ) : (
        <div className="space-y-3">
          {rows.map((r) => (
            <div key={r.id} className="bg-white ring-1 ring-black/5 shadow-[var(--shadow-card)] flex flex-wrap items-center justify-between gap-3 rounded-3xl p-4 sm:p-5">
              <div className="min-w-0">
                <p className="truncate font-semibold">{r.user_name}</p>
                <p className="truncate text-sm text-neutral-500">{r.user_email}</p>
                <p className="mt-1 text-xs text-neutral-400">Registered {new Date(r.created_at).toLocaleDateString("en-IN")} · Payment: {r.payment_status}</p>
              </div>
              <div className="flex items-center gap-2">
                <Pill tone={tone[r.approval_status]}>{label[r.approval_status]}</Pill>
                {r.approval_status === "pending" && (
                  <>
                    <Button size="sm" onClick={() => decide(r.id, true)}>Approve</Button>
                    <Button size="sm" variant="outline" onClick={() => decide(r.id, false)}>Reject</Button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
