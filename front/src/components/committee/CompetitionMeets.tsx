"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Auction, ClMeet, ClMeetTask, CompetitionSettings, Contingent } from "@/lib/types";
import { formatDay, formatTime } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";
import { labelOf, useRun } from "./CompetitionBoard";

const when = (iso: string) => `${formatDay(iso.slice(0, 10))}, ${formatTime(iso.slice(11, 16))}`;
const inputLocal = (iso: string) => iso.slice(0, 16);

/** Record what each contingent earned for a task. Picking 1st, 2nd, 3rd fills the usual points, and any amount can still be typed. */
function ResultForm({ slug, meet, task, people, onDone }: { slug: string; meet: ClMeet; task: ClMeetTask; people: Contingent[]; onDone: () => void }) {
  const initial = Object.fromEntries(task.results.map((r) => [r.contingent_id, String(r.points)]));
  const [pts, setPts] = useState<Record<number, string>>(initial);
  const [place, setPlace] = useState<string[]>(["", "", ""]);
  const { run, error, busy } = useRun(onDone);
  const scheme = task.placing_points ?? [];
  const pick = (i: number, id: string) => {
    const next = [...place]; next[i] = id; setPlace(next);
    setPts((cur) => {
      const out = { ...cur };
      for (const k of Object.keys(out)) if (place.includes(k) && !next.includes(k)) delete out[Number(k)];
      next.forEach((cid, n) => { if (cid && scheme[n] !== undefined) out[Number(cid)] = String(scheme[n]); });
      return out;
    });
  };
  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const awards = Object.entries(pts).filter(([, v]) => v !== "" && Number(v) !== 0).map(([id, v]) => ({ contingent_id: Number(id), points: Number(v) }));
    run(() => api(`/api/fests/${slug}/cl-meets/${meet.id}/tasks/${task.id}/result`, { method: "PUT", body: { awards } }));
  };
  return (
    <form onSubmit={save} className="mt-3 space-y-4 rounded-2xl bg-wash p-4">
      <ErrorNote>{error}</ErrorNote>
      {scheme.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-3">
          {scheme.slice(0, 3).map((p, i) => (
            <Field key={i} label={`${["1st", "2nd", "3rd"][i]} place (+${p})`}>
              <select className="field" value={place[i]} onChange={(e) => pick(i, e.target.value)}><option value="">Nobody</option>{people.map((c) => <option key={c.id} value={c.id} disabled={place.includes(String(c.id)) && place[i] !== String(c.id)}>{labelOf(c)}</option>)}</select>
            </Field>
          ))}
        </div>
      )}
      <div>
        <p className="mb-1.5 text-[13px] font-semibold">Points for each contingent <span className="font-normal text-mute">(leave empty for none, minus to take off)</span></p>
        <ul className="grid gap-2 sm:grid-cols-2">
          {people.map((c) => (
            <li key={c.id} className="flex items-center gap-2 rounded-xl bg-white px-3 py-2 ring-1 ring-black/10">
              <span className="min-w-0 flex-1 truncate text-sm">{labelOf(c)}</span>
              <input aria-label={`Points for ${labelOf(c)}`} className="field !h-9 !w-24" type="number" value={pts[c.id] ?? ""} onChange={(e) => setPts({ ...pts, [c.id]: e.target.value })} />
            </li>
          ))}
        </ul>
      </div>
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy}>{busy ? "Saving…" : "Save result"}</Button><Button size="sm" type="button" variant="ghost" onClick={onDone}>Cancel</Button></div>
    </form>
  );
}

function MeetCard({ slug, meet, people, usual, reload }: { slug: string; meet: ClMeet; people: Contingent[]; usual: string; reload: () => void }) {
  const [adding, setAdding] = useState(false);
  const [scoring, setScoring] = useState<number | null>(null);
  const [showAttendance, setShowAttendance] = useState(false);
  const [t, setT] = useState({ title: "", description: "", placing: usual });
  const { run, error, busy } = useRun(reload);
  const addTask = async (e: React.FormEvent) => {
    e.preventDefault();
    const placing_points = t.placing.split(/[,\s]+/).filter(Boolean).map(Number);
    if (await run(() => api(`/api/fests/${slug}/cl-meets/${meet.id}/tasks`, { method: "POST", body: { title: t.title, description: t.description || null, placing_points: placing_points.length ? placing_points : null } }))) { setAdding(false); setT({ title: "", description: "", placing: usual }); }
  };
  const toggleCame = (id: number) => {
    const next = meet.attended.includes(id) ? meet.attended.filter((x) => x !== id) : [...meet.attended, id];
    run(() => api(`/api/fests/${slug}/cl-meets/${meet.id}/attendance`, { method: "PUT", body: { contingent_ids: next } }));
  };
  return (
    <article className="card p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0"><h3 className="font-display text-lg font-semibold">{meet.title}</h3><p className="text-[13px] text-mute">{when(meet.starts_at)}{meet.location ? ` · ${meet.location}` : ""}</p>{meet.notes && <p className="mt-1 text-sm">{meet.notes}</p>}</div>
        <div className="flex gap-3 text-[13px] font-semibold"><button onClick={() => setShowAttendance(!showAttendance)} className="underline underline-offset-4">Who came ({meet.attended.length}/{people.length})</button>
          <button disabled={busy} onClick={() => window.confirm(`Delete “${meet.title}”? The points its tasks gave out come off again.`) && run(() => api(`/api/fests/${slug}/cl-meets/${meet.id}`, { method: "DELETE" }))} className="text-red-600 hover:underline">Delete</button></div>
      </div>
      <div className="mt-2"><ErrorNote>{error}</ErrorNote></div>
      {showAttendance && <ul className="mt-3 grid gap-1.5 sm:grid-cols-2">{people.map((c) => <li key={c.id}><label className="flex items-center gap-2 rounded-xl bg-wash px-3 py-2 text-sm"><input type="checkbox" checked={meet.attended.includes(c.id)} disabled={busy} onChange={() => toggleCame(c.id)} />{labelOf(c)}</label></li>)}</ul>}

      <div className="mt-5 space-y-3">
        {meet.tasks.length === 0 && <p className="text-sm text-mute">No tasks yet. Add the games and challenges for this meet.</p>}
        {meet.tasks.map((task) => (
          <div key={task.id} className="rounded-2xl border border-[var(--ws-border)] p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0"><p className="font-semibold">{task.title}</p>{task.description && <p className="text-sm text-mute">{task.description}</p>}{task.placing_points && <p className="text-[12px] text-mute">Usual points: {task.placing_points.join(", ")}</p>}</div>
              <div className="flex gap-3 text-[13px] font-semibold"><button onClick={() => setScoring(scoring === task.id ? null : task.id)} className="underline underline-offset-4">{task.results.length ? "Change result" : "Record result"}</button>
                <button disabled={busy} onClick={() => window.confirm(`Delete “${task.title}”? Any points it gave out come off again.`) && run(() => api(`/api/fests/${slug}/cl-meets/${meet.id}/tasks/${task.id}`, { method: "DELETE" }))} className="text-red-600 hover:underline">Delete</button></div>
            </div>
            {task.results.length > 0 && <p className="mt-2 flex flex-wrap gap-2 text-[13px]">{task.results.map((r) => <Pill key={r.contingent_id} tone={r.points < 0 ? "red" : "green"}>{r.contingent_label} {r.points > 0 ? "+" : ""}{r.points}</Pill>)}</p>}
            {scoring === task.id && <ResultForm slug={slug} meet={meet} task={task} people={people} onDone={() => { setScoring(null); reload(); }} />}
          </div>
        ))}
        {adding ? (
          <form onSubmit={addTask} className="space-y-3 rounded-2xl bg-wash p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Task"><input className="field" required autoFocus maxLength={200} value={t.title} onChange={(e) => setT({ ...t, title: e.target.value })} placeholder="e.g. Treasure hunt" /></Field>
              <Field label="Usual points for 1st, 2nd, 3rd" hint="Optional. You can still award any amount."><input className="field" value={t.placing} onChange={(e) => setT({ ...t, placing: e.target.value })} /></Field>
            </div>
            <Field label="What is it?"><input className="field" maxLength={2000} value={t.description} onChange={(e) => setT({ ...t, description: e.target.value })} /></Field>
            <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy || !t.title.trim()}>Add task</Button><Button size="sm" type="button" variant="ghost" onClick={() => setAdding(false)}>Cancel</Button></div>
          </form>
        ) : <Button size="sm" variant="outline" onClick={() => setAdding(true)}>Add a task</Button>}
      </div>
    </article>
  );
}

/** CL meets: when they are, the tasks the committee runs, who came, and who earned what. */
export function MeetsPanel({ slug, people }: { slug: string; people: Contingent[] }) {
  const [meets, setMeets] = useState<ClMeet[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState({ title: "", starts_at: "", location: "", notes: "" });
  const [usual, setUsual] = useState("200, 100, 50");
  const load = useCallback(() => { api<ClMeet[]>(`/api/fests/${slug}/cl-meets`).then(setMeets).catch(() => setMeets([])); }, [slug]);
  useEffect(() => { load(); api<CompetitionSettings>(`/api/fests/${slug}/competition/settings`).then((s) => setUsual(s.default_task_points.join(", "))).catch(() => {}); }, [load, slug]);
  const { run, error, busy } = useRun(load);
  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await run(() => api(`/api/fests/${slug}/cl-meets`, { method: "POST", body: { title: f.title, starts_at: f.starts_at, location: f.location || null, notes: f.notes || null } }))) { setAdding(false); setF({ title: "", starts_at: "", location: "", notes: "" }); }
  };
  if (!meets) return <Skeleton className="h-40" />;
  return (
    <div className="max-w-4xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-mute">Meetings of the contingent leaders before the fest. Run tasks, and the points go straight onto each contingent.</p><Button size="sm" onClick={() => setAdding(!adding)}>{adding ? "Close" : "Schedule a CL meet"}</Button></div>
      <ErrorNote>{error}</ErrorNote>
      {adding && (
        <form onSubmit={add} className="card grid gap-4 p-5 sm:grid-cols-2">
          <Field label="Name"><input className="field" required maxLength={200} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="e.g. CL meet 1" /></Field>
          <Field label="When"><input className="field" type="datetime-local" required value={f.starts_at} onChange={(e) => setF({ ...f, starts_at: e.target.value })} /></Field>
          <Field label="Where"><input className="field" maxLength={255} value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} /></Field>
          <Field label="Notes for the leaders"><input className="field" maxLength={5000} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
          <div className="sm:col-span-2"><Button type="submit" disabled={busy || !f.title.trim() || !f.starts_at}>Schedule</Button></div>
        </form>
      )}
      {meets.length === 0 && !adding ? <EmptyState title="No CL meets yet" body="Schedule the first one, add its tasks, and record who wins what." /> : meets.map((m) => <MeetCard key={m.id} slug={slug} meet={m} people={people} usual={usual} reload={load} />)}
    </div>
  );
}

/** One name auction: names go up, contingents bid points, the highest bid on each wins and only that bid is paid. */
function AuctionCard({ slug, a, people, reload }: { slug: string; a: Auction; people: Contingent[]; reload: () => void }) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [bidFor, setBidFor] = useState<Record<number, { c: string; amount: string }>>({});
  const { run, error, busy } = useRun(reload);
  const base = `/api/fests/${slug}/auctions/${a.id}`;
  const tone = a.status === "open" ? "green" : a.status === "closed" ? "neutral" : "amber";
  const bid = (nid: number) => {
    const b = bidFor[nid]; if (!b?.c || !b.amount) return;
    run(async () => { await api(`${base}/names/${nid}/bid`, { method: "PUT", body: { contingent_id: Number(b.c), amount: Number(b.amount) } }); setBidFor((x) => ({ ...x, [nid]: { c: b.c, amount: "" } })); });
  };
  return (
    <article className="card p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h3 className="flex flex-wrap items-center gap-2 font-display text-lg font-semibold">{a.title}<Pill tone={tone}>{a.status === "draft" ? "Not open" : a.status === "open" ? "Open for bids" : "Closed"}</Pill></h3>
          <p className="text-[13px] text-mute">Smallest bid {a.min_bid} · {a.show_highest_bid ? "leaders see the top bid" : "bids are sealed"} · only the winning bid is paid</p></div>
        <div className="flex flex-wrap gap-2">
          {a.status === "draft" && <Button size="sm" disabled={busy || a.names.length === 0} onClick={() => run(() => api(`${base}/open`, { method: "POST" }))}>Open for bids</Button>}
          {a.status === "open" && <Button size="sm" disabled={busy} onClick={() => window.confirm("Close the auction? The highest bid on each name wins it, and only winning bids are taken off.") && run(() => api(`${base}/close`, { method: "POST" }))}>Close and settle</Button>}
          {a.status === "closed" && <Button size="sm" variant="outline" disabled={busy} onClick={() => window.confirm("Reopen? The points paid come back and the names are taken off.") && run(() => api(`${base}/reopen`, { method: "POST" }))}>Reopen</Button>}
          {a.status !== "closed" && <button disabled={busy} onClick={() => window.confirm(`Delete “${a.title}”?`) && run(() => api(base, { method: "DELETE" }))} className="px-2 text-[13px] font-semibold text-red-600 hover:underline">Delete</button>}
        </div>
      </div>
      <div className="mt-2"><ErrorNote>{error}</ErrorNote></div>

      <ul className="mt-4 space-y-3">
        {a.names.map((n) => (
          <li key={n.id} className="rounded-2xl border border-[var(--ws-border)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold">{n.name}{n.code && <span className="ml-2 text-[12px] font-normal text-mute">{n.code}</span>}</p>
              {a.status === "closed" ? <p className="text-sm">{n.winner_label ? <><strong>{n.winner_label}</strong> won it for {n.winning_bid} points</> : <span className="text-mute">Nobody won it</span>}</p>
                : a.status === "draft" ? <button disabled={busy} onClick={() => run(() => api(`${base}/names/${n.id}`, { method: "DELETE" }))} className="text-[13px] font-semibold text-red-600 hover:underline">Remove</button> : null}
            </div>
            {a.status !== "draft" && (
              <>
                {n.bids.length > 0 ? <ul className="mt-2 flex flex-wrap gap-2 text-[13px]">{n.bids.map((b, i) => <li key={b.contingent_id}><Pill tone={i === 0 && a.status === "open" ? "green" : "neutral"}>{b.contingent_label} · {b.amount}</Pill></li>)}</ul> : <p className="mt-2 text-[13px] text-mute">No bids yet.</p>}
                {a.status === "open" && (
                  <div className="mt-3 flex flex-wrap items-end gap-2">
                    <select aria-label="Contingent bidding" className="field !h-10 !w-auto min-w-[10rem]" value={bidFor[n.id]?.c ?? ""} onChange={(e) => setBidFor({ ...bidFor, [n.id]: { c: e.target.value, amount: bidFor[n.id]?.amount ?? "" } })}><option value="">Bid for…</option>{people.map((c) => <option key={c.id} value={c.id}>{labelOf(c)}</option>)}</select>
                    <input aria-label="Bid" className="field !h-10 !w-28" type="number" min={a.min_bid} placeholder="Points" value={bidFor[n.id]?.amount ?? ""} onChange={(e) => setBidFor({ ...bidFor, [n.id]: { c: bidFor[n.id]?.c ?? "", amount: e.target.value } })} />
                    <Button size="sm" variant="outline" disabled={busy || !bidFor[n.id]?.c || !bidFor[n.id]?.amount} onClick={() => bid(n.id)}>Place bid</Button>
                  </div>
                )}
              </>
            )}
          </li>
        ))}
      </ul>
      {a.status === "draft" && (
        <form onSubmit={async (e) => { e.preventDefault(); if (await run(() => api(`${base}/names`, { method: "POST", body: { name, code: code || null } }))) { setName(""); setCode(""); } }} className="mt-4 flex flex-wrap items-end gap-3">
          <div className="min-w-[12rem] flex-1"><Field label="Add a name to bid for"><input className="field" required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Phoenix" /></Field></div>
          <div className="w-32"><Field label="Code (optional)"><input className="field" maxLength={30} value={code} onChange={(e) => setCode(e.target.value)} placeholder="PHX" /></Field></div>
          <Button type="submit" size="sm" disabled={busy || !name.trim()}>Add</Button>
        </form>
      )}
    </article>
  );
}

/** The name auction. The committee sets the names, the leaders bid, and the winners get their names. */
export function AuctionPanel({ slug, people }: { slug: string; people: Contingent[] }) {
  const [list, setList] = useState<Auction[] | null>(null);
  const [meets, setMeets] = useState<ClMeet[]>([]);
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState({ title: "", min_bid: "1", meet_id: "", sealed: true });
  const load = useCallback(() => { api<Auction[]>(`/api/fests/${slug}/auctions`).then(setList).catch(() => setList([])); }, [slug]);
  useEffect(() => { load(); api<ClMeet[]>(`/api/fests/${slug}/cl-meets`).then(setMeets).catch(() => {}); }, [load, slug]);
  const { run, error, busy } = useRun(load);
  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await run(() => api(`/api/fests/${slug}/auctions`, { method: "POST", body: { title: f.title, min_bid: Number(f.min_bid) || 0, meet_id: f.meet_id ? Number(f.meet_id) : null, show_highest_bid: !f.sealed } }))) { setAdding(false); setF({ title: "", min_bid: "1", meet_id: "", sealed: true }); }
  };
  if (!list) return <Skeleton className="h-40" />;
  return (
    <div className="max-w-4xl space-y-5">
      <Notice tone="info">The highest bid on each name wins it. A contingent wins at most one name, and only its winning bid comes off its points. Everyone else keeps theirs.</Notice>
      <div className="flex justify-end"><Button size="sm" onClick={() => setAdding(!adding)}>{adding ? "Close" : "New auction"}</Button></div>
      <ErrorNote>{error}</ErrorNote>
      {adding && (
        <form onSubmit={add} className="card grid gap-4 p-5 sm:grid-cols-2">
          <Field label="Name of the auction"><input className="field" required maxLength={200} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="e.g. Contingent names" /></Field>
          <Field label="Smallest bid (points)"><input className="field" type="number" min={0} value={f.min_bid} onChange={(e) => setF({ ...f, min_bid: e.target.value })} /></Field>
          <Field label="Held at"><select className="field" value={f.meet_id} onChange={(e) => setF({ ...f, meet_id: e.target.value })}><option value="">No particular meet</option>{meets.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}</select></Field>
          <label className="flex items-start gap-2 self-end pb-2 text-sm"><input type="checkbox" className="mt-1" checked={f.sealed} onChange={(e) => setF({ ...f, sealed: e.target.checked })} /><span><strong>Sealed bids</strong><span className="block text-mute">Leaders see only their own bids, not the top one.</span></span></label>
          <div className="sm:col-span-2"><Button type="submit" disabled={busy || !f.title.trim()}>Create</Button></div>
        </form>
      )}
      {list.length === 0 && !adding ? <EmptyState title="No auctions yet" body="Make one, add the names and codes up for bidding, open it at the CL meet, then close it to settle the winners." /> : list.map((a) => <AuctionCard key={a.id} slug={slug} a={a} people={people} reload={load} />)}
    </div>
  );
}
