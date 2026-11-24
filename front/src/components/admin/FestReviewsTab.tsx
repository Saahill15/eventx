"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FestReview, ReviewFieldNote } from "@/lib/types";
import { REVIEW_FIELDS, reviewFieldLabel } from "@/lib/reviewFields";
import { formatDay, formatTime, mapsLink } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Notice, Pill, Skeleton } from "@/components/ui/bits";
import { Chips, Detail, useAction, useCounts, when } from "./shared";

const FILTERS = [
  { id: "in_review", label: "In review" }, { id: "changes_requested", label: "Changes requested" },
  { id: "approved", label: "Approved" }, { id: "rejected", label: "Rejected" },
] as const;
type Filter = (typeof FILTERS)[number]["id"];
const tone = { in_review: "amber", changes_requested: "amber", approved: "green", rejected: "red", draft: "neutral" } as const;

/** Write a note, and/or flag specific parts of the fest with a short note each, so the organiser can see exactly what to fix. */
function DecisionForm({ placeholder, submitLabel, busy, onSubmit, onCancel }: {
  placeholder: string; submitLabel: string; busy: boolean; onSubmit: (note: string, fields: ReviewFieldNote[]) => void; onCancel: () => void;
}) {
  const [note, setNote] = useState("");
  const [flags, setFlags] = useState<Record<string, string>>({});
  const flagged = Object.keys(flags);
  const toggle = (key: string) => setFlags((f) => { const next = { ...f }; if (key in next) delete next[key]; else next[key] = ""; return next; });
  const noteOk = note.trim() === "" || note.trim().length >= 5;
  const valid = noteOk && (note.trim().length >= 5 || flagged.length > 0) && flagged.every((k) => flags[k].trim().length > 0);

  return (
    <div className="space-y-4">
      <fieldset>
        <legend className="mb-2 text-sm font-semibold">Flag what needs fixing <span className="font-normal text-mute">(optional)</span></legend>
        <ul className="space-y-2">
          {REVIEW_FIELDS.map((f) => (
            <li key={f.key}>
              <label className="flex items-center gap-3 text-sm font-medium"><input type="checkbox" className="h-4 w-4 accent-[#111]" checked={f.key in flags} onChange={() => toggle(f.key)} />{f.label}</label>
              {f.key in flags && <input className="field mt-2" aria-label={`What to change about: ${f.label}`} autoFocus placeholder={`What should they change about the ${f.label.toLowerCase()}?`} maxLength={300} value={flags[f.key]} onChange={(e) => setFlags((x) => ({ ...x, [f.key]: e.target.value }))} />}
            </li>
          ))}
        </ul>
      </fieldset>
      <label className="block">
        <span className="mb-1.5 block text-sm font-semibold">General note {flagged.length > 0 && <span className="font-normal text-mute">(optional)</span>}</span>
        <textarea className="field min-h-20" placeholder={placeholder} value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
      </label>
      <div className="flex gap-2">
        <Button size="sm" disabled={busy || !valid} onClick={() => onSubmit(note.trim(), flagged.map((key) => ({ key: key as ReviewFieldNote["key"], note: flags[key].trim() })))}>{submitLabel}</Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

function FestCard({ r, onDone }: { r: FestReview; onDone: () => void }) {
  const [open, setOpen] = useState(r.fest.review_status === "in_review");
  const [mode, setMode] = useState<"" | "request-changes" | "reject" | "unpublish">("");
  const act = useAction(onDone);
  const f = r.fest;
  const decide = (kind: "approve" | "request-changes" | "reject" | "unpublish", note = "", fields: ReviewFieldNote[] = []) =>
    act.run(async () => {
      await api(`/api/admin/fests/${f.slug}/${kind}`, { method: "POST", body: kind === "approve" ? undefined : { note: note || null, fields } });
      setMode("");
    });

  return (
    <div className="card p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Pill tone={tone[f.review_status as keyof typeof tone] ?? "neutral"}>{FILTERS.find((x) => x.id === f.review_status)?.label ?? f.review_status}</Pill>
            {f.status === "live" && <Pill tone="green">Live</Pill>}
            {r.college && <span className="text-xs font-medium text-mute">{r.college.name}</span>}
          </div>
          <p className="font-display text-2xl font-bold tracking-tight">{f.name}</p>
          {f.tagline && <p className="text-mute">{f.tagline}</p>}
          <p className="mt-1 text-xs text-mute">{f.submitted_at ? `Submitted ${when(f.submitted_at)}` : "Not submitted yet"} · {r.events.length} event{r.events.length === 1 ? "" : "s"}</p>
        </div>
        <Button size="sm" variant="outline" onClick={() => setOpen((v) => !v)}>{open ? "Hide details" : "Review details"}</Button>
      </div>

      {open && (
        <div className="mt-6 space-y-6 border-t border-black/5 pt-6">
          {r.missing.length > 0 && <Notice tone="warn"><strong>Incomplete:</strong> {r.missing.join(" · ")}</Notice>}
          {f.review_note && <Notice tone="info"><strong>Last note:</strong> {f.review_note}</Notice>}
          {(f.review_fields ?? []).length > 0 && (
            <Notice tone="info"><strong>Flagged last time:</strong> {(f.review_fields ?? []).map((x) => `${reviewFieldLabel(x.key)}: ${x.note}`).join(" · ")}</Notice>
          )}

          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Detail label="Dates">{f.start_date && f.end_date ? `${f.start_date} → ${f.end_date}` : f.dates_tba ? "Coming soon (not fixed yet)" : ""}</Detail>
            <Detail label="Campus address">{f.campus_address}</Detail>
            <Detail label="Map">{(f.map_url || f.campus_address) && <a className="underline" href={f.map_url || mapsLink(f.campus_address ?? "")} target="_blank" rel="noopener noreferrer">Open map</a>}</Detail>
            <Detail label="Committee contact">{[f.contact_name, f.contact_phone, f.contact_email].filter(Boolean).join(" · ")}</Detail>
            <Detail label="Faculty coordinator">{[f.faculty_name, f.faculty_phone, f.faculty_email].filter(Boolean).join(" · ")}</Detail>
            <Detail label="Directors">{r.owners.join(", ")}</Detail>
            <Detail label="Short link">{r.short_link ? `/${r.short_link}` : ""}</Detail>
            <Detail label="College partnership">{r.college ? `${r.college.partner_status === "partner" ? "Partner" : "Prospect"}${r.college.coordinator_name ? ` · ${r.college.coordinator_name}` : ""}${r.college.coordinator_phone ? ` · ${r.college.coordinator_phone}` : ""}` : "No college linked"}</Detail>
          </dl>
          {f.description && <p className="whitespace-pre-line text-sm text-neutral-700">{f.description}</p>}

          {r.events.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-mute">Events</p>
              <ul className="divide-y divide-black/5 rounded-2xl bg-wash px-4">
                {r.events.map((e) => <li key={e.id} className="flex flex-wrap justify-between gap-2 py-2.5 text-sm"><span className="font-medium">{e.title}</span><span className="text-mute">{formatDay(e.date)} · {formatTime(e.time)}{e.end_time ? `–${formatTime(e.end_time)}` : ""} · {e.location ?? "No venue"}</span></li>)}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <Link href={`/dashboard/fests/${f.slug}`} className="inline-flex h-9 items-center rounded-full bg-white px-4 text-sm font-semibold shadow-[var(--shadow-card)] hover:bg-wash">Open the fest as its organisers see it</Link>
            {f.status === "live" && <Link href={`/fests/${f.slug}`} className="inline-flex h-9 items-center rounded-full bg-white px-4 text-sm font-semibold shadow-[var(--shadow-card)] hover:bg-wash">Public page</Link>}
          </div>

          <ChangeDirector slug={f.slug} onDone={onDone} />

          {f.review_status === "approved" && (
            <div className="space-y-3 border-t border-black/5 pt-5">
              <ErrorNote>{act.error}</ErrorNote>
              {mode === "unpublish" ? (
                <DecisionForm placeholder="Why is it being taken offline? The organiser will see this and can fix and resubmit." submitLabel="Take offline" busy={act.busy} onCancel={() => setMode("")} onSubmit={(n, fl) => decide("unpublish", n, fl)} />
              ) : <Button size="sm" variant="outline" onClick={() => setMode("unpublish")}>Take offline and send back</Button>}
            </div>
          )}

          {f.review_status === "in_review" && (
            <div className="space-y-3 border-t border-black/5 pt-5">
              <ErrorNote>{act.error}</ErrorNote>
              {mode && mode !== "unpublish" ? (
                <DecisionForm placeholder={mode === "reject" ? "Why is this being rejected? The organiser will see this." : "Anything else the organiser should know?"} submitLabel={mode === "reject" ? "Reject fest" : "Send back"} busy={act.busy} onCancel={() => setMode("")} onSubmit={(n, fl) => decide(mode, n, fl)} />
              ) : (
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" disabled={act.busy || r.missing.length > 0} onClick={() => decide("approve")}>Approve</Button>
                  <Button size="sm" variant="outline" onClick={() => setMode("request-changes")}>Request changes</Button>
                  <Button size="sm" variant="outline" onClick={() => setMode("reject")}>Reject</Button>
                  {r.missing.length > 0 && <span className="self-center text-xs text-mute">Cannot approve while details are missing.</span>}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Admin: make another organiser this fest's director straight away (for example when the director has left). */
function ChangeDirector({ slug, onDone }: { slug: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [keep, setKeep] = useState(true);
  const act = useAction(onDone);
  if (!open) return <button onClick={() => setOpen(true)} className="text-sm font-semibold underline underline-offset-4">Change director</button>;
  return (
    <div className="space-y-3 rounded-2xl bg-wash p-4">
      <ErrorNote>{act.error}</ErrorNote>
      <input className="field" type="email" placeholder="New director's email (an organiser for this college)" value={email} onChange={(e) => setEmail(e.target.value)} />
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-[#111]" checked={keep} onChange={(e) => setKeep(e.target.checked)} /> Keep the current director on as core team</label>
      <div className="flex gap-2">
        <Button size="sm" disabled={act.busy || !email.includes("@")} onClick={async () => { if (await act.run(() => api(`/api/admin/fests/${slug}/owner`, { method: "POST", body: { email: email.trim(), keep_previous_owner: keep } }))) { setOpen(false); setEmail(""); } }}>Make director now</Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </div>
  );
}

export function FestReviewsTab() {
  const o = useCounts();
  const counts: Partial<Record<Filter, number>> = { in_review: o?.fests_in_review, changes_requested: o?.fests_changes_requested };
  const [filter, setFilter] = useState<Filter>("in_review");
  const [rows, setRows] = useState<FestReview[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    api<FestReview[]>(`/api/admin/fests?review_status=${filter}`).then((r) => { setRows(r); setError(""); }).catch((e) => { setError(e instanceof Error ? e.message : "Could not load."); setRows([]); });
  }, [filter]);
  useEffect(() => { setRows(null); load(); }, [load]);

  return (
    <div>
      <Chips value={filter} onChange={setFilter} options={FILTERS.map((f) => ({ id: f.id, label: f.label, count: counts[f.id] }))} />
      <ErrorNote>{error}</ErrorNote>
      {rows === null ? <Skeleton className="h-40" /> : rows.length === 0 ? (
        <EmptyState title="Nothing here" body={filter === "in_review" ? "No fests are waiting for review." : "No fests with this status."} />
      ) : <div className="space-y-4">{rows.map((r) => <FestCard key={r.fest.id} r={r} onDone={load} />)}</div>}
    </div>
  );
}
