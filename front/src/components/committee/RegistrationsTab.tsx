"use client";

import { useCallback, useEffect, useState } from "react";
import { Download } from "lucide-react";
import { api, downloadFile } from "@/lib/api";
import type { ManagedEvent, RegistrationDetail } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Pill, Skeleton } from "@/components/ui/bits";
import { Chips } from "@/components/admin/shared";

const tone = { approved: "green", pending: "amber", rejected: "red" } as const;
const label = { approved: "Confirmed", pending: "Waiting", rejected: "Rejected" } as const;
type Filter = "all" | "pending" | "approved" | "rejected";

export function RegistrationsTab({ events, reload }: { events: ManagedEvent[]; reload: () => void }) {
  const withReg = events.filter((e) => e.requires_registration);
  const [eventId, setEventId] = useState<number | null>(withReg.find((e) => e.pending_count > 0)?.id ?? withReg[0]?.id ?? null);
  const [rows, setRows] = useState<RegistrationDetail[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
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

  if (withReg.length === 0) return <EmptyState title="No events take registrations yet" body='Turn on "Students must register" when you add or edit an event.' />;

  const count = (s: string) => rows?.filter((r) => r.approval_status === s).length ?? 0;
  const shown = (rows ?? []).filter((r) => filter === "all" || r.approval_status === filter);

  return (
    <div className="max-w-4xl">
      <div className="mb-5 flex flex-wrap items-end gap-3">
        <label className="min-w-[220px] flex-1">
          <span className="mb-1.5 block text-sm font-semibold">Event</span>
          <select className="field" value={eventId ?? ""} onChange={(e) => { setEventId(Number(e.target.value)); setFilter("all"); }}>
            {withReg.map((e) => <option key={e.id} value={e.id}>{e.title}{e.pending_count ? ` (${e.pending_count} waiting)` : ""}</option>)}
          </select>
        </label>
        <Button variant="outline" onClick={exportCsv} disabled={!rows || rows.length === 0}><Download className="h-4 w-4" /> Download CSV</Button>
      </div>
      <ErrorNote>{error}</ErrorNote>
      {rows && <div className="mt-4"><Chips value={filter} onChange={setFilter} options={[{ id: "all", label: `All ${rows.length}` }, { id: "pending", label: "Waiting", count: count("pending") }, { id: "approved", label: `Confirmed ${count("approved")}` }, { id: "rejected", label: `Rejected ${count("rejected")}` }]} /></div>}

      {rows === null ? <Skeleton className="h-24" /> : shown.length === 0 ? (
        <EmptyState title={rows.length === 0 ? "Nobody has registered yet" : "Nothing here"} body={rows.length === 0 ? "Registrations appear here as students sign up." : "No registrations with this status."} />
      ) : (
        <div className="space-y-3">
          {shown.map((r) => (
            <div key={r.id} className="card p-4 sm:p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-semibold">{r.user_name}</p>
                  <p className="truncate text-sm text-mute">{r.user_email}</p>
                  <p className="mt-1 text-xs text-mute">Registered {new Date(r.created_at).toLocaleDateString("en-IN")} · Payment: {r.payment_status}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {r.checked_in && <Pill tone="green">Attended</Pill>}
                  <Pill tone={tone[r.approval_status]}>{label[r.approval_status]}</Pill>
                  {r.approval_status === "pending" && (<><Button size="sm" onClick={() => decide(r.id, true)}>Approve</Button><Button size="sm" variant="outline" onClick={() => decide(r.id, false)}>Reject</Button></>)}
                </div>
              </div>
              {r.answers.length > 0 && <dl className="mt-3 grid gap-x-6 gap-y-1 rounded-2xl bg-wash p-3 text-sm sm:grid-cols-2">{r.answers.map((a) => <div key={a.question_id}><dt className="text-xs text-mute">{a.label}</dt><dd className="font-medium">{a.answer}</dd></div>)}</dl>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
