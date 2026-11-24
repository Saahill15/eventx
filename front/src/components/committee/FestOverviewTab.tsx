"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Circle } from "lucide-react";
import { api } from "@/lib/api";
import type { ChecklistItem, FestManage, FestStats } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Notice, Skeleton } from "@/components/ui/bits";
import { Stat } from "@/components/admin/shared";
import { ReviewPill } from "./CommitteeShell";
import { ShortLinkCard } from "./ShortLinkCard";

const STEPS = [
  { id: "draft", label: "Build your fest" }, { id: "in_review", label: "HiveOut reviews it" }, { id: "approved", label: "Approved" }, { id: "live", label: "Live for students" },
];

/** The journey of a fest, what is still missing, and the buttons that move it along: submit, withdraw, go live. */
export function FestOverviewTab({ fest, role, reload, goTo }: { fest: FestManage; role: string; reload: () => void; goTo: (tab: string) => void }) {
  const [missing, setMissing] = useState<string[] | null>(null);
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [stats, setStats] = useState<FestStats | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const canSubmit = role === "owner" || role === "core" || role === "admin";
  const status = fest.review_status;

  const load = useCallback(() => {
    api<{ missing: string[]; items: ChecklistItem[] }>(`/api/fests/${fest.slug}/manage/checklist`).then((r) => { setMissing(r.missing); setItems(r.items); }).catch(() => { setMissing([]); setItems([]); });
    api<FestStats>(`/api/fests/${fest.slug}/manage/stats`).then(setStats).catch(() => {});
  }, [fest.slug]);
  useEffect(load, [load, fest.review_status, fest.status]);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); reload(); load(); } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); }
    setBusy(false);
  };
  const post = (action: string) => run(() => api(`/api/fests/${fest.slug}/${action}`, { method: "POST" }));
  const setLive = (live: boolean) => run(() => api(`/api/fests/${fest.slug}/status`, { method: "PATCH", body: { status: live ? "live" : "draft" } }));

  const required = items.filter((i) => i.required);
  const doneCount = required.filter((i) => i.done).length;
  const next = required.find((i) => !i.done);
  const ready = missing !== null && missing.length === 0;

  const stage = fest.status === "live" ? 3 : status === "approved" ? 2 : status === "in_review" ? 1 : 0;
  const pending = stats?.events.reduce((n, e) => n + e.pending, 0) ?? 0;

  return (
    <div className="max-w-4xl space-y-6">
      <ol className="card flex flex-wrap gap-x-8 gap-y-3 p-6">
        {STEPS.map((s, i) => (
          <li key={s.id} className={`flex items-center gap-2.5 text-sm font-semibold ${i <= stage ? "text-ink" : "text-mute"}`}>
            <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs ${i < stage ? "bg-emerald-500 text-white" : i === stage ? "bg-ink text-white" : "bg-wash"}`}>{i < stage ? <Check className="h-3.5 w-3.5" /> : i + 1}</span>
            {s.label}
          </li>
        ))}
      </ol>

      <ErrorNote>{error}</ErrorNote>

      {(status === "changes_requested" || status === "rejected") && fest.review_note && (
        <Notice tone="warn"><strong>{status === "rejected" ? "HiveOut rejected this fest:" : "HiveOut asked for changes:"}</strong> {fest.review_note}</Notice>
      )}

      {fest.status === "live" ? (
        <section className="card flex flex-wrap items-center justify-between gap-4 p-6">
          <div><div className="flex items-center gap-2"><ReviewPill status={status} /><span className="rounded-full bg-mint px-2.5 py-1 text-xs font-semibold text-emerald-800">Live</span></div><p className="mt-2 text-mute">Students can see your fest and get entry passes.</p></div>
          {canSubmit && <Button variant="outline" disabled={busy} onClick={() => setLive(false)}>Take offline</Button>}
        </section>
      ) : status === "approved" ? (
        <section className="card flex flex-wrap items-center justify-between gap-4 p-6">
          <div><ReviewPill status={status} /><p className="mt-2 text-mute">HiveOut approved your fest. Go live when you are ready for students to find it.</p></div>
          {canSubmit && <Button size="lg" disabled={busy} onClick={() => setLive(true)}>Make fest live</Button>}
        </section>
      ) : status === "in_review" ? (
        <section className="card flex flex-wrap items-center justify-between gap-4 p-6">
          <div><ReviewPill status={status} /><p className="mt-2 text-mute">HiveOut is reviewing your fest. Details and events are locked until they decide. You will see the result here.</p></div>
          {canSubmit && <Button variant="outline" disabled={busy} onClick={() => post("withdraw")}>Withdraw to edit</Button>}
        </section>
      ) : (
        <section className="card space-y-5 p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <ReviewPill status={status} />
              <h2 className="mt-3 font-display text-xl font-semibold tracking-tight">{ready ? "You are ready to send it for review" : "Get your fest ready"}</h2>
              <p className="mt-1 text-mute">{missing === null ? "Checking…" : ready ? "Everything is filled in. HiveOut will review it and let you know." : "A few quick steps, then HiveOut reviews your fest. Everything saves as you go."}</p>
            </div>
            {canSubmit && <Button size="lg" disabled={busy || missing === null || missing.length > 0} onClick={() => post("submit")}>Send for review</Button>}
          </div>

          {required.length > 0 && (
            <div>
              <div className="mb-2 flex items-baseline justify-between text-sm"><span className="font-semibold">{doneCount} of {required.length} done</span><span className="text-mute">About a minute each</span></div>
              <div className="h-2 overflow-hidden rounded-full bg-wash" role="progressbar" aria-valuemin={0} aria-valuemax={required.length} aria-valuenow={doneCount} aria-label="Steps done">
                <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${(doneCount / required.length) * 100}%` }} />
              </div>
            </div>
          )}

          <ol className="divide-y divide-black/10">
            {items.map((it) => {
              const isNext = next?.key === it.key;
              return (
                <li key={it.key} className="flex items-start gap-4 py-4">
                  <span className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs ${it.done ? "bg-emerald-500 text-white" : isNext ? "bg-ink text-white" : "bg-wash text-mute"}`} aria-hidden="true">{it.done ? <Check className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />}</span>
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm font-semibold ${it.done ? "text-mute line-through decoration-1" : ""}`}>{it.label}{!it.required && <span className="ml-2 rounded-full bg-wash px-2 py-0.5 text-xs font-medium text-mute no-underline">Optional</span>}</p>
                    {!it.done && it.hint && <p className="mt-0.5 text-sm text-mute">{it.hint}</p>}
                    {!it.done && it.problems.length > 0 && <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-sm text-mute">{it.problems.map((p) => <li key={p}>{p}</li>)}</ul>}
                  </div>
                  {canSubmit && !it.done && <Button size="sm" variant={isNext ? "ink" : "outline"} onClick={() => goTo(it.tab)}>{it.key === "dates" ? "Set dates" : it.key === "events" ? "Add event" : it.key === "team" ? "Invite" : "Fill in"}</Button>}
                  {canSubmit && it.done && <button onClick={() => goTo(it.tab)} className="text-xs font-semibold text-mute underline underline-offset-4 hover:text-ink">Edit</button>}
                </li>
              );
            })}
          </ol>
        </section>
      )}

      {canSubmit && <ShortLinkCard slug={fest.slug} live={fest.status === "live"} />}

      {stats ? (
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(14rem,1fr))]">
          <Stat label="Entry passes" value={stats.passes_issued} hint={`${stats.passes_checked_in} checked in`} />
          <Stat label="Events" value={stats.events.length} />
          <Stat label="Registrations to approve" value={pending} tone="alert" onClick={pending ? () => goTo("registrations") : undefined} />
        </div>
      ) : <Skeleton className="h-24" />}
    </div>
  );
}
