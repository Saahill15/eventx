"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Award, Breakdown, CompetitionSettings, Contingent, ContingentStanding, Leaderboard, PointsEntry, ScoredEvent } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";

/** A contingent's name, or its college when it has none yet. Two contingents of one college are told apart by their leader. */
export const labelOf = (c: { name: string | null; college_name: string; leader_name?: string | null }) => c.name || (c.leader_name ? `${c.college_name} (${c.leader_name})` : c.college_name);
const signed = (n: number) => (n > 0 ? `+${n}` : String(n));

/** Run an action, keep its error for display and refresh afterwards. */
export function useRun(after: () => void) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const run = useCallback(async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); after(); return true; } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); return false; } finally { setBusy(false); }
  }, [after]);
  return { run, error, busy, setError };
}

const KIND: Record<keyof Breakdown, string> = { meet_tasks: "CL meet tasks", auction: "Name auction", event_points: "Event wins", penalties: "Penalties", adjustments: "Adjustments" };

function Breakdowns({ b, start }: { b: Breakdown; start: number }) {
  const parts = (Object.keys(KIND) as (keyof Breakdown)[]).filter((k) => b[k] !== 0);
  return (
    <p className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[12px] text-mute">
      <span>Start {start}</span>
      {parts.map((k) => <span key={k} className={b[k] < 0 ? "text-red-600" : ""}>{KIND[k]} {signed(b[k])}</span>)}
    </p>
  );
}

function StandingRow({ r, slug, leader, reload }: { r: ContingentStanding; slug: string; leader?: string | null; reload: () => void }) {
  const [mode, setMode] = useState<"" | "adjust" | "history">("");
  const [points, setPoints] = useState("");
  const [reason, setReason] = useState("");
  const [ledger, setLedger] = useState<PointsEntry[] | null>(null);
  const { run, error, busy } = useRun(reload);
  const toggle = (m: "adjust" | "history") => {
    setMode(mode === m ? "" : m);
    if (m === "history" && mode !== "history") api<PointsEntry[]>(`/api/fests/${slug}/competition/ledger?contingent_id=${r.contingent_id}`).then(setLedger).catch(() => setLedger([]));
  };
  const adjust = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await run(() => api(`/api/fests/${slug}/competition/adjustments`, { method: "POST", body: { contingent_id: r.contingent_id, points: Number(points), reason } }))) { setPoints(""); setReason(""); setMode(""); }
  };
  return (
    <li className={`card p-4 ${r.disqualified ? "opacity-60" : ""}`}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-chip text-[14px] font-bold">{r.rank ?? "–"}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{labelOf(r)}{r.code && <span className="ml-2 text-[12px] font-normal text-mute">{r.code}</span>}{r.disqualified && <span className="ml-2"><Pill tone="red">Disqualified</Pill></span>}</p>
          <p className="truncate text-[13px] text-mute">{r.name ? r.college_name : "No name yet"}{leader ? ` · led by ${leader}` : ""}</p>
          <Breakdowns b={r.breakdown} start={r.starting_points} />
        </div>
        <div className="text-right"><p className="text-[22px] font-semibold leading-none">{r.balance}</p><p className="text-[12px] text-mute">points</p></div>
        <div className="flex gap-3 text-[13px] font-semibold"><button onClick={() => toggle("adjust")} className="underline underline-offset-4">Adjust</button><button onClick={() => toggle("history")} className="underline underline-offset-4">History</button></div>
      </div>
      {mode === "adjust" && (
        <form onSubmit={adjust} className="mt-3 grid gap-3 rounded-xl bg-wash p-3 sm:grid-cols-[120px_1fr_auto] sm:items-end">
          <Field label="Points" hint="Minus takes off"><input className="field" type="number" required value={points} onChange={(e) => setPoints(e.target.value)} placeholder="e.g. -20" /></Field>
          <Field label="Why"><input className="field" required minLength={3} maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          <Button size="sm" type="submit" disabled={busy || !points || Number(points) === 0}>Save</Button>
        </form>
      )}
      {mode === "adjust" && <div className="mt-2"><ErrorNote>{error}</ErrorNote></div>}
      {mode === "history" && (
        <ul className="mt-3 divide-y divide-[var(--ws-border)] rounded-xl bg-wash px-3 text-[13px]">
          {ledger === null ? <li className="py-3 text-mute">Loading…</li> : ledger.length === 0 ? <li className="py-3 text-mute">Nothing yet beyond the starting {r.starting_points} points.</li> : ledger.map((e) => (
            <li key={e.id} className="flex justify-between gap-3 py-2"><span className="min-w-0 truncate">{e.reason}</span><span className={`shrink-0 font-semibold ${e.points < 0 ? "text-red-600" : "text-emerald-700"}`}>{signed(e.points)}</span></li>
          ))}
        </ul>
      )}
    </li>
  );
}

/** Where every contingent and every college stands right now. */
export function StandingsPanel({ slug, people }: { slug: string; people: Contingent[] }) {
  const [board, setBoard] = useState<Leaderboard | null>(null);
  const load = useCallback(() => { api<Leaderboard>(`/api/fests/${slug}/competition/leaderboard`).then(setBoard).catch(() => setBoard({ ranking_basis: "total", contingents: [], colleges: [], awards: [] })); }, [slug]);
  useEffect(() => { load(); }, [load]);
  if (!board) return <Skeleton className="h-40" />;
  if (people.length === 0) return <EmptyState title="No contingents are taking part yet" body="Visiting colleges appear here once the committee approves them. Each starts with the fest's starting points." />;
  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <section aria-label="Contingents" className="min-w-0 space-y-3">
        <p className="text-sm text-mute">{board.ranking_basis === "events" ? "Ranked by what events earned." : "Ranked by the points each contingent holds."} Use Adjust for a correction, History to see every change.</p>
        <ul className="space-y-3">{board.contingents.map((r) => <StandingRow key={r.contingent_id} r={r} slug={slug} leader={people.find((p) => p.id === r.contingent_id)?.leader_name} reload={load} />)}</ul>
      </section>
      <section aria-label="Colleges" className="card overflow-hidden">
        <div className="flex h-12 items-center border-b border-[var(--ws-border)] px-5"><h2 className="text-[14px] font-semibold">Colleges</h2></div>
        <ul>
          {board.colleges.map((c) => (
            <li key={c.college_name} className="flex items-center gap-3 border-b border-[var(--ws-border)] px-5 py-3 last:border-b-0">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-chip text-[13px] font-bold">{c.rank}</span>
              <div className="min-w-0 flex-1"><p className="truncate text-[14px] font-semibold">{c.college_name}</p>{c.contingents > 1 && <p className="truncate text-[12px] text-mute">{c.contingents} contingents added together</p>}</div>
              <p className="font-semibold">{c.score}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

/** The fest's prizes. Most are worked out from the standings; a custom one is given by hand. */
export function AwardsPanel({ slug, people, events }: { slug: string; people: Contingent[]; events: ScoredEvent[] }) {
  const [awards, setAwards] = useState<Award[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState({ title: "", basis: "college", rank: "1", event_id: "", winner: "" });
  const load = useCallback(() => { api<Award[]>(`/api/fests/${slug}/competition/awards`).then(setAwards).catch(() => setAwards([])); }, [slug]);
  useEffect(() => { load(); }, [load]);
  const { run, error, busy } = useRun(load);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF((x) => ({ ...x, [k]: e.target.value }));
  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    const body = { title: f.title, basis: f.basis, rank: Number(f.rank), event_id: f.basis === "event" ? Number(f.event_id) : null, winner_contingent_id: f.basis === "custom" && f.winner ? Number(f.winner) : null };
    if (await run(() => api(`/api/fests/${slug}/competition/awards`, { method: "POST", body }))) { setAdding(false); setF({ title: "", basis: "college", rank: "1", event_id: "", winner: "" }); }
  };
  if (!awards) return <Skeleton className="h-40" />;
  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-mute">Winners are worked out live from the standings. A college award adds up all of a college&apos;s contingents.</p>
        <div className="flex gap-2">{awards.length === 0 && <Button size="sm" variant="outline" disabled={busy} onClick={() => run(() => api(`/api/fests/${slug}/competition/awards/usual`, { method: "POST" }))}>Add the usual awards</Button>}<Button size="sm" onClick={() => setAdding(!adding)}>{adding ? "Close" : "Add an award"}</Button></div>
      </div>
      <ErrorNote>{error}</ErrorNote>
      {adding && (
        <form onSubmit={add} className="card grid gap-4 p-5 sm:grid-cols-2">
          <Field label="Award name"><input className="field" required maxLength={120} value={f.title} onChange={set("title")} placeholder="e.g. Best College" /></Field>
          <Field label="Given to">
            <select className="field" value={f.basis} onChange={set("basis")}><option value="college">A college, by rank</option><option value="contingent">A contingent, by rank</option><option value="event">The winner of one event</option><option value="custom">Someone I choose</option></select>
          </Field>
          {f.basis !== "custom" && <Field label="Rank" hint="1 is the winner, 2 the runner-up"><input className="field" type="number" min={1} max={20} value={f.rank} onChange={set("rank")} /></Field>}
          {f.basis === "event" && <Field label="Event"><select className="field" required value={f.event_id} onChange={set("event_id")}><option value="">Choose</option>{events.map((e) => <option key={e.event_id} value={e.event_id}>{e.title}</option>)}</select></Field>}
          {f.basis === "custom" && <Field label="Winner"><select className="field" value={f.winner} onChange={set("winner")}><option value="">Decide later</option>{people.map((c) => <option key={c.id} value={c.id}>{labelOf(c)}</option>)}</select></Field>}
          <div className="sm:col-span-2"><Button type="submit" disabled={busy || !f.title.trim()}>Add award</Button></div>
        </form>
      )}
      {awards.length === 0 && !adding ? <EmptyState title="No awards yet" body="Add the usual best college, runner-up and third place in one click, or make your own." /> : (
        <ul className="space-y-3">
          {awards.map((a) => (
            <li key={a.id} className="card flex flex-wrap items-center justify-between gap-3 p-4">
              <div className="min-w-0"><p className="font-semibold">{a.title}</p><p className="text-[13px] text-mute">{a.basis === "college" ? `College ranked ${a.rank}` : a.basis === "contingent" ? `Contingent ranked ${a.rank}` : a.basis === "event" ? `Place ${a.rank} in ${a.event_title}` : "Chosen by the committee"}</p></div>
              <div className="text-right"><p className="font-semibold">{a.winners.length ? a.winners.map((w) => w.name).join(" and ") : <span className="font-normal text-mute">No winner yet</span>}</p></div>
              <button disabled={busy} onClick={() => window.confirm(`Remove the “${a.title}” award?`) && run(() => api(`/api/fests/${slug}/competition/awards/${a.id}`, { method: "DELETE" }))} className="text-[13px] font-semibold text-red-600 hover:underline">Remove</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The scoring rules: what everyone starts with, what the ranking counts, and whether the board is public. */
export function SettingsPanel({ slug }: { slug: string }) {
  const [s, setS] = useState<CompetitionSettings | null>(null);
  const [places, setPlaces] = useState("");
  const [taskPts, setTaskPts] = useState("");
  const [saved, setSaved] = useState(false);
  const load = useCallback(() => { api<CompetitionSettings>(`/api/fests/${slug}/competition/settings`).then((r) => { setS(r); setPlaces(r.default_placing_points.join(", ")); setTaskPts(r.default_task_points.join(", ")); }); }, [slug]);
  useEffect(() => { load(); }, [load]);
  const { run, error, busy } = useRun(() => setSaved(true));
  if (!s) return <Skeleton className="h-40" />;
  const save = (e: React.FormEvent) => {
    e.preventDefault(); setSaved(false);
    const nums = (t: string) => t.split(/[,\s]+/).filter(Boolean).map(Number);
    run(() => api(`/api/fests/${slug}/competition/settings`, { method: "PUT", body: { starting_points: s.starting_points, ranking_basis: s.ranking_basis, public_leaderboard: s.public_leaderboard, default_placing_points: nums(places), default_task_points: nums(taskPts) } }));
  };
  return (
    <form onSubmit={save} className="card max-w-2xl space-y-5 p-6">
      <Notice tone="info">Every number here is your choice. The values shown are only a usual starting point, and each CL task, event, rule and award can still use its own.</Notice>
      <ErrorNote>{error}</ErrorNote>
      {saved && <Notice tone="ok">Saved.</Notice>}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Starting points" hint="What every contingent begins with. Changing it moves everyone's balance by the same amount."><input className="field" type="number" min={0} max={100000} value={s.starting_points} onChange={(e) => setS({ ...s, starting_points: Number(e.target.value) })} /></Field>
        <Field label="The ranking counts" hint="Awards use this.">
          <select className="field" value={s.ranking_basis} onChange={(e) => setS({ ...s, ranking_basis: e.target.value as "total" | "events" })}><option value="total">The whole balance (what is left after bidding)</option><option value="events">Only what events earned</option></select>
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Usual points for an event: 1st, 2nd, 3rd…" hint="Offered when you make an event a competition. Each event can change them."><input className="field" value={places} onChange={(e) => setPlaces(e.target.value)} placeholder="100, 60, 30" /></Field>
        <Field label="Usual points for a CL meet task: 1st, 2nd, 3rd…" hint="Offered when you add a task. Each task can change them."><input className="field" value={taskPts} onChange={(e) => setTaskPts(e.target.value)} placeholder="200, 100, 50" /></Field>
      </div>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={s.public_leaderboard} onChange={(e) => setS({ ...s, public_leaderboard: e.target.checked })} />
        <span><strong>Show the leaderboard and awards on the public fest page</strong><span className="block text-mute">Leaders then see their rank too. Leave it off until you are happy with the standings.</span></span></label>
      <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</Button>
    </form>
  );
}
