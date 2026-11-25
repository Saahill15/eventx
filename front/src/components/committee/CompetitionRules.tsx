"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CompetitionRule, Contingent, Penalty, ScoredEvent } from "@/lib/types";
import { formatDay } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";
import { labelOf, useRun } from "./CompetitionBoard";

const ordinal = (n: number) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;

interface Row { place: number; contingent: string; note: string }

/** Who placed where in one scored event. The points for each place were set on the event. */
function ResultCard({ slug, ev, people, reload }: { slug: string; ev: ScoredEvent; people: Contingent[]; reload: () => void }) {
  const places = Object.keys(ev.points_scheme ?? {}).map(Number).sort((a, b) => a - b);
  const start = (): Row[] => ev.results.length ? ev.results.map((r) => ({ place: r.place, contingent: String(r.contingent_id), note: r.note ?? "" })) : places.map((p) => ({ place: p, contingent: "", note: "" }));
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState<Row[]>(start);
  const { run, error, busy } = useRun(() => { setEditing(false); reload(); });
  const used = rows.map((r) => r.contingent).filter(Boolean);
  const save = (e: React.FormEvent) => {
    e.preventDefault();
    run(() => api(`/api/fests/${slug}/competition/events/${ev.event_id}/results`, { method: "PUT", body: { results: rows.filter((r) => r.contingent).map((r) => ({ contingent_id: Number(r.contingent), place: r.place, note: r.note || null })) } }));
  };
  return (
    <article className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h3 className="font-semibold">{ev.title}</h3><p className="text-[12px] text-mute">Points: {places.map((p) => `${ordinal(p)} ${ev.points_scheme?.[String(p)]}`).join(" · ")}</p></div>
        <button onClick={() => { setRows(start()); setEditing(!editing); }} className="text-[13px] font-semibold underline underline-offset-4">{editing ? "Close" : ev.results.length ? "Change result" : "Record result"}</button>
      </div>
      {!editing && ev.results.length > 0 && (
        <ul className="mt-3 space-y-1.5 text-sm">
          {ev.results.map((r) => <li key={r.contingent_id} className={`flex flex-wrap items-center gap-x-3 ${r.disqualified ? "text-mute line-through" : ""}`}><span className="w-10 font-semibold">{ordinal(r.place)}</span><span>{r.contingent_label}</span>{r.note && <span className="text-mute">· {r.note}</span>}<span className="ml-auto font-semibold">{r.disqualified ? "Disqualified" : `+${r.points}`}</span></li>)}
        </ul>
      )}
      {editing && (
        <form onSubmit={save} className="mt-3 space-y-3 rounded-2xl bg-wash p-4">
          <ErrorNote>{error}</ErrorNote>
          {rows.map((r, i) => (
            <div key={i} className="grid items-end gap-2 sm:grid-cols-[90px_1fr_1fr_auto]">
              <Field label="Place"><input className="field" type="number" min={1} max={20} value={r.place} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, place: Number(e.target.value) } : x))} /></Field>
              <Field label="Contingent"><select className="field" value={r.contingent} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, contingent: e.target.value } : x))}><option value="">Nobody</option>{people.map((c) => <option key={c.id} value={c.id} disabled={used.includes(String(c.id)) && r.contingent !== String(c.id)}>{labelOf(c)}</option>)}</select></Field>
              <Field label="Who won (for the record)"><input className="field" maxLength={300} value={r.note} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, note: e.target.value } : x))} /></Field>
              <button type="button" onClick={() => setRows(rows.filter((_, j) => j !== i))} className="pb-2 text-[13px] font-semibold text-red-600 hover:underline">Remove</button>
            </div>
          ))}
          <div className="flex flex-wrap gap-2"><Button size="sm" type="submit" disabled={busy}>{busy ? "Saving…" : "Save result"}</Button><Button size="sm" type="button" variant="outline" onClick={() => setRows([...rows, { place: Math.max(0, ...rows.map((r) => r.place)) + 1, contingent: "", note: "" }])}>Add a place</Button></div>
        </form>
      )}
    </article>
  );
}

export function ResultsPanel({ slug, people, events, reload }: { slug: string; people: Contingent[]; events: ScoredEvent[] | null; reload: () => void }) {
  if (!events) return <Skeleton className="h-40" />;
  if (events.length === 0) return <EmptyState title="No scored events yet" body="Open an event under Events and turn on “A competition between colleges”, then set the points for each place. It shows up here for you to record who won." />;
  return <div className="max-w-3xl space-y-4"><p className="text-sm text-mute">Record who placed where. Each contingent gets the points for its place. A disqualified result shows struck through and earns nothing.</p>{events.map((ev) => <ResultCard key={ev.event_id} slug={slug} ev={ev} people={people} reload={reload} />)}</div>;
}

/** One rule, with its cost, and a form to change anything about it. */
function RuleRow({ slug, rule, events, busy, run }: { slug: string; rule: CompetitionRule; events: ScoredEvent[]; busy: boolean; run: (fn: () => Promise<unknown>) => Promise<boolean> }) {
  const [editing, setEditing] = useState(false);
  const [f, setF] = useState({ title: rule.title, description: rule.description ?? "", points: String(rule.penalty_points), disq: rule.disqualifies, event: rule.event_id ? String(rule.event_id) : "" });
  const cost = [rule.penalty_points ? `−${rule.penalty_points} points` : null, rule.disqualifies ? "disqualifies" : null].filter(Boolean).join(" and ") || "no penalty";
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await run(() => api(`/api/fests/${slug}/competition/rules/${rule.id}`, { method: "PATCH", body: { title: f.title, description: f.description || null, penalty_points: Number(f.points) || 0, disqualifies: f.disq, event_id: f.event ? Number(f.event) : null } }))) setEditing(false);
  };
  if (editing) {
    return (
      <li className="card p-4">
        <form onSubmit={save} className="space-y-3">
          <Field label="Rule"><input className="field" required maxLength={200} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
          <Field label="Details"><input className="field" maxLength={2000} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Points taken off"><input className="field" type="number" min={0} value={f.points} onChange={(e) => setF({ ...f, points: e.target.value })} /></Field>
            <Field label="Applies to"><select className="field" value={f.event} onChange={(e) => setF({ ...f, event: e.target.value })}><option value="">Every event</option>{events.map((ev) => <option key={ev.event_id} value={ev.event_id}>{ev.title}</option>)}</select></Field>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.disq} onChange={(e) => setF({ ...f, disq: e.target.checked })} />Breaking it means disqualification</label>
          <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy || !f.title.trim()}>Save</Button><Button size="sm" type="button" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button></div>
        </form>
      </li>
    );
  }
  return (
    <li className="card flex flex-wrap items-start justify-between gap-3 p-4">
      <div className="min-w-0"><p className="font-semibold">{rule.title}</p>{rule.description && <p className="text-sm text-mute">{rule.description}</p>}<p className="mt-1 text-[12px] text-mute">{rule.event_title ?? "Every event"} · {cost}</p></div>
      <div className="flex gap-3 text-[13px] font-semibold"><button onClick={() => setEditing(true)} className="underline underline-offset-4">Edit</button>
        <button disabled={busy} onClick={() => window.confirm(`Delete the rule “${rule.title}”? Penalties already given stay on record.`) && run(() => api(`/api/fests/${slug}/competition/rules/${rule.id}`, { method: "DELETE" }))} className="text-red-600 hover:underline">Delete</button></div>
    </li>
  );
}

/** The rules of the competition and what breaking them costs, penalties given, and appeals. */
export function RulesPanel({ slug, people, events, reload }: { slug: string; people: Contingent[]; events: ScoredEvent[]; reload: () => void }) {
  const [rules, setRules] = useState<CompetitionRule[] | null>(null);
  const [penalties, setPenalties] = useState<Penalty[]>([]);
  const load = useCallback(() => {
    api<CompetitionRule[]>(`/api/fests/${slug}/competition/rules`).then(setRules).catch(() => setRules([]));
    api<Penalty[]>(`/api/fests/${slug}/competition/penalties`).then(setPenalties).catch(() => {});
    reload();
  }, [slug, reload]);
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const { run, error, busy } = useRun(load);
  const [r, setR] = useState({ title: "", description: "", points: "0", disq: false, event: "" });
  const [p, setP] = useState({ contingent: "", rule: "", event: "", points: "", disq: false, reason: "" });
  const [showRule, setShowRule] = useState(false);

  const chooseRule = (id: string) => {
    const rule = rules?.find((x) => String(x.id) === id);
    setP((x) => ({ ...x, rule: id, ...(rule ? { points: rule.penalty_points ? String(rule.penalty_points) : "", disq: rule.disqualifies, event: rule.event_id ? String(rule.event_id) : x.event, reason: x.reason || rule.title } : {}) }));
  };
  const addRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await run(() => api(`/api/fests/${slug}/competition/rules`, { method: "POST", body: { title: r.title, description: r.description || null, penalty_points: Number(r.points) || 0, disqualifies: r.disq, event_id: r.event ? Number(r.event) : null } }))) { setShowRule(false); setR({ title: "", description: "", points: "0", disq: false, event: "" }); }
  };
  const apply = async (e: React.FormEvent) => {
    e.preventDefault();
    const body = { contingent_id: Number(p.contingent), rule_id: p.rule ? Number(p.rule) : null, event_id: p.event ? Number(p.event) : null, points: p.points === "" ? null : Number(p.points), disqualified: p.disq, reason: p.reason || null };
    if (await run(() => api(`/api/fests/${slug}/competition/penalties`, { method: "POST", body }))) setP({ contingent: "", rule: "", event: "", points: "", disq: false, reason: "" });
  };
  if (!rules) return <Skeleton className="h-40" />;

  return (
    <div className="grid items-start gap-6 xl:grid-cols-2">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-[15px] font-semibold">Rules <span className="font-normal text-mute">{rules.length}</span></h2>
          <div className="flex gap-2">{rules.length < 5 && <Button size="sm" variant="outline" disabled={busy} onClick={() => run(() => api(`/api/fests/${slug}/competition/rules/usual`, { method: "POST" }))}>Add the usual rules</Button>}<Button size="sm" variant="outline" onClick={() => setShowRule(!showRule)}>{showRule ? "Close" : "Add a rule"}</Button></div></div>
        <p className="-mt-2 text-[13px] text-mute">Every fest has its own rules and penalties. The usual rules are just a start: change the wording and the points, or delete any.</p>
        <ErrorNote>{error}</ErrorNote>
        {showRule && (
          <form onSubmit={addRule} className="card space-y-3 p-4">
            <Field label="Rule"><input className="field" required maxLength={200} value={r.title} onChange={(e) => setR({ ...r, title: e.target.value })} placeholder="e.g. Late arrival" /></Field>
            <Field label="Details"><input className="field" maxLength={2000} value={r.description} onChange={(e) => setR({ ...r, description: e.target.value })} /></Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Points taken off"><input className="field" type="number" min={0} value={r.points} onChange={(e) => setR({ ...r, points: e.target.value })} /></Field>
              <Field label="Applies to"><select className="field" value={r.event} onChange={(e) => setR({ ...r, event: e.target.value })}><option value="">Every event</option>{events.map((ev) => <option key={ev.event_id} value={ev.event_id}>{ev.title}</option>)}</select></Field>
            </div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={r.disq} onChange={(e) => setR({ ...r, disq: e.target.checked })} />Breaking it means disqualification</label>
            <Button size="sm" type="submit" disabled={busy || !r.title.trim()}>Add rule</Button>
          </form>
        )}
        {rules.length === 0 && !showRule ? <p className="text-sm text-mute">No rules yet. Add the usual set and edit it, or write your own, so giving a penalty later is a single click.</p> : (
          <ul className="space-y-2">{rules.map((x) => <RuleRow key={x.id} slug={slug} rule={x} events={events} busy={busy} run={run} />)}</ul>
        )}
      </div>

      <div className="space-y-4">
        <h2 className="text-[15px] font-semibold">Give a penalty</h2>
        <form onSubmit={apply} className="card space-y-3 p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Contingent"><select className="field" required value={p.contingent} onChange={(e) => setP({ ...p, contingent: e.target.value })}><option value="">Choose</option>{people.map((c) => <option key={c.id} value={c.id}>{labelOf(c)}</option>)}</select></Field>
            <Field label="Rule" hint="Optional. It fills in the rest."><select className="field" value={p.rule} onChange={(e) => chooseRule(e.target.value)}><option value="">No rule, my own reason</option>{rules.map((x) => <option key={x.id} value={x.id}>{x.title}</option>)}</select></Field>
            <Field label="Points taken off"><input className="field" type="number" min={0} value={p.points} onChange={(e) => setP({ ...p, points: e.target.value })} /></Field>
            <Field label="In event" hint="Leave empty for the whole competition"><select className="field" value={p.event} onChange={(e) => setP({ ...p, event: e.target.value })}><option value="">Not tied to one event</option>{events.map((ev) => <option key={ev.event_id} value={ev.event_id}>{ev.title}</option>)}</select></Field>
          </div>
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={p.disq} onChange={(e) => setP({ ...p, disq: e.target.checked })} /><span><strong>Disqualify</strong><span className="block text-mute">{p.event ? "From that event: its points no longer count." : "From the whole competition: left out of the rankings and awards."} Lifting the penalty later undoes it.</span></span></label>
          <Field label="Why"><input className="field" maxLength={500} value={p.reason} onChange={(e) => setP({ ...p, reason: e.target.value })} placeholder="Shown to the contingent's leaders" /></Field>
          <Button size="sm" type="submit" disabled={busy || !p.contingent || (!p.reason && !p.rule) || (!p.disq && !(Number(p.points) > 0))}>Apply penalty</Button>
        </form>
        <h2 className="pt-2 text-[15px] font-semibold">Given so far <span className="font-normal text-mute">{penalties.length}</span></h2>
        {penalties.length === 0 ? <p className="text-sm text-mute">None.</p> : (
          <ul className="space-y-2">{penalties.map((x) => (
            <li key={x.id} className={`card p-4 ${x.revoked ? "opacity-60" : ""}`}>
              <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold">{x.contingent_label}{x.revoked && <span className="ml-2"><Pill tone="neutral">Lifted</Pill></span>}</p>
                {!x.revoked && <button disabled={busy} onClick={() => window.confirm("Lift this penalty? Its points come back and a disqualification is undone.") && run(() => api(`/api/fests/${slug}/competition/penalties/${x.id}`, { method: "DELETE" }))} className="text-[13px] font-semibold underline underline-offset-4">Lift (appeal accepted)</button>}</div>
              <p className="text-sm">{x.reason}</p>
              <p className="text-[12px] text-mute">{[x.points ? `−${x.points} points` : null, x.disqualified ? (x.event_title ? `disqualified from ${x.event_title}` : "disqualified from the competition") : null, formatDay(x.created_at.slice(0, 10))].filter(Boolean).join(" · ")}</p>
            </li>
          ))}</ul>
        )}
      </div>
      {!people.length && <div className="xl:col-span-2"><Notice tone="info">No contingents are taking part yet, so there is nobody to penalise.</Notice></div>}
    </div>
  );
}
