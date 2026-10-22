"use client";

import { useCallback, useEffect, useState } from "react";
import { api, openFile } from "@/lib/api";
import type { VerificationReview } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Notice, Skeleton } from "@/components/ui/bits";
import { Chips, useAction, when } from "./shared";

type Filter = "pending" | "approved" | "rejected";

function Row({ v, onDone }: { v: VerificationReview; onDone: () => void }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const act = useAction(onDone);
  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold">{v.user_name ?? "Unknown"} <span className="font-normal text-mute">· {v.user_email}</span></p>
          <p className="text-sm text-mute">{v.college_name ?? "No college"} · {v.document_type ?? "Proof"} · sent {when(v.created_at)}</p>
        </div>
        {v.status === "pending" && (
          <div className="flex flex-wrap gap-2">
            {v.has_file && <Button size="sm" variant="outline" onClick={() => act.run(() => openFile(`/api/admin/student-verifications/${v.id}/file`))}>View document</Button>}
            <Button size="sm" disabled={act.busy} onClick={() => act.run(() => api(`/api/admin/student-verifications/${v.id}/approve`, { method: "POST" }))}>Approve</Button>
            <Button size="sm" variant="outline" onClick={() => setRejecting((x) => !x)}>Reject</Button>
          </div>
        )}
      </div>
      {rejecting && (
        <div className="mt-4 flex flex-wrap gap-2">
          <input className="field min-w-0 flex-1" placeholder="Reason shown to the student" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
          <Button size="sm" disabled={act.busy || reason.trim().length < 3} onClick={() => act.run(() => api(`/api/admin/student-verifications/${v.id}/reject`, { method: "POST", body: { reason } }))}>Send rejection</Button>
        </div>
      )}
      <div className="mt-3"><ErrorNote>{act.error}</ErrorNote></div>
    </div>
  );
}

export function VerificationsTab() {
  const [filter, setFilter] = useState<Filter>("pending");
  const [rows, setRows] = useState<VerificationReview[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    api<VerificationReview[]>(`/api/admin/student-verifications?status=${filter}`).then((r) => { setRows(r); setError(""); }).catch((e) => { setError(e instanceof Error ? e.message : "Could not load."); setRows([]); });
  }, [filter]);
  useEffect(() => { setRows(null); load(); }, [load]);

  return (
    <div>
      <Notice tone="info">Students who cannot use a college email upload a photo of their ID. The photo is deleted the moment you decide.</Notice>
      <div className="mt-5" />
      <Chips value={filter} onChange={setFilter} options={[{ id: "pending", label: "Pending" }, { id: "approved", label: "Approved" }, { id: "rejected", label: "Rejected" }]} />
      <ErrorNote>{error}</ErrorNote>
      {rows === null ? <Skeleton className="h-32" /> : rows.length === 0 ? <EmptyState title="Nothing here" body={filter === "pending" ? "No proofs are waiting." : "No verifications with this status."} /> : <div className="space-y-3">{rows.map((v) => <Row key={v.id} v={v} onDone={load} />)}</div>}
    </div>
  );
}
