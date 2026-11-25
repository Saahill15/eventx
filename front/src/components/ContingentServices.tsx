"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ContingentMember, EnterableEvent, EventEntry, FeeStatement, MyEntries, MyStay, PaymentConfig } from "@/lib/types";
import { formatDay, formatTime, inr } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { PayNow } from "./PayNow";
import { ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";

function useRun(after: () => void) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const run = useCallback(async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); after(); return true; } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); return false; } finally { setBusy(false); }
  }, [after]);
  return { run, error, busy };
}

// ─── events the contingent enters ────────────────────────────────────────────

function Picker({ members, picked, setPicked, limit, taken }: { members: ContingentMember[]; picked: number[]; setPicked: (p: number[]) => void; limit: number; taken: number[] }) {
  const toggle = (id: number) => setPicked(picked.includes(id) ? picked.filter((x) => x !== id) : picked.length >= limit ? (limit === 1 ? [id] : picked) : [...picked, id]);
  return (
    <div className="grid gap-1.5 sm:grid-cols-2">
      {members.map((m) => {
        const on = picked.includes(m.id);
        const used = taken.includes(m.id) && !on;
        return <label key={m.id} className={`flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-sm ring-1 ${on ? "ring-2 ring-ink" : "ring-black/10"} ${used ? "opacity-50" : ""}`}><input type={limit === 1 ? "radio" : "checkbox"} name={`pick-${limit}`} checked={on} disabled={used} onChange={() => toggle(m.id)} /><span className="min-w-0 truncate">{m.name}{used && <span className="text-mute"> · already in this event</span>}</span></label>;
      })}
    </div>
  );
}

function EntryForm({ slug, ev, members, entry, taken, onDone }: { slug: string; ev: EnterableEvent; members: ContingentMember[]; entry?: EventEntry; taken: number[]; onDone: () => void }) {
  const [picked, setPicked] = useState<number[]>(entry?.members.map((m) => m.member_id) ?? []);
  const { run, error, busy } = useRun(onDone);
  const high = ev.is_team_event ? ev.team_max ?? 100 : 1;
  const low = ev.is_team_event ? ev.team_min ?? 1 : 1;
  const ok = picked.length >= low && picked.length <= high;
  return (
    <form onSubmit={(e) => { e.preventDefault(); run(() => entry ? api(`/api/fests/${slug}/entries/${entry.id}`, { method: "PUT", body: { member_ids: picked } }) : api(`/api/fests/${slug}/entries`, { method: "POST", body: { event_id: ev.event_id, member_ids: picked } })); }} className="mt-3 space-y-3 rounded-2xl bg-wash p-4">
      <ErrorNote>{error}</ErrorNote>
      <p className="text-sm font-semibold">{ev.is_team_event ? `Choose the team: ${low}${low === high ? "" : ` to ${high}`} people` : "Choose who takes part"} <span className="font-normal text-mute">({picked.length} chosen)</span></p>
      <Picker members={members} picked={picked} setPicked={setPicked} limit={high} taken={taken} />
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy || !ok}>{entry ? "Save" : "Enter"}{ev.entry_fee ? ` · ${inr(ev.entry_fee_per === "participant" ? ev.entry_fee * picked.length : ev.entry_fee)}` : ""}</Button><Button size="sm" type="button" variant="ghost" onClick={onDone}>Cancel</Button></div>
    </form>
  );
}

/** The events a visiting college can enter, and the entries it has made. Each entry names the people from its list who take part. */
export function EntriesPortal({ slug, members }: { slug: string; members: ContingentMember[] }) {
  const [d, setD] = useState<MyEntries | null | undefined>(undefined);
  const [form, setForm] = useState<{ event: number; entry?: number } | null>(null);
  const load = useCallback(() => { api<MyEntries | null>(`/api/fests/${slug}/entries/mine`).then(setD).catch(() => setD(null)); }, [slug]);
  useEffect(() => { load(); }, [load]);
  const { run, error, busy } = useRun(load);
  if (d === undefined) return <Skeleton className="h-32" />;
  if (!d || d.events.length === 0) return null;
  const active = d.entries.filter((x) => x.status === "confirmed");
  const takenIn = (eventId: number, exceptEntry?: number) => active.filter((x) => x.event_id === eventId && x.id !== exceptEntry).flatMap((x) => x.members.map((m) => m.member_id));
  const rule = (e: EnterableEvent) => `${e.is_team_event ? `Team of ${e.team_min ?? 1}${e.team_max && e.team_max !== e.team_min ? `–${e.team_max}` : ""}` : "One person"} · up to ${e.entries_per_contingent} entr${e.entries_per_contingent === 1 ? "y" : "ies"} · ${e.entry_fee ? `${inr(e.entry_fee)} ${e.entry_fee_per === "participant" ? "each person" : "an entry"}` : "free"}${e.deadline ? ` · enter by ${formatDay(e.deadline)}` : ""}`;
  return (
    <section className="card space-y-5 p-6 sm:p-8" aria-label="Events">
      <div><h3 className="font-display text-xl font-bold tracking-tight">Events you are entering</h3><p className="mt-1 text-sm text-mute">Pick an event, then choose who from your list takes part. The cost is added to your fees.</p></div>
      <ErrorNote>{error}</ErrorNote>
      {members.length === 0 && <Notice tone="info">Add the people on your team to your list below first, then you can enter them in events.</Notice>}
      <ul className="space-y-3">
        {d.events.map((ev) => {
          const mine = active.filter((x) => x.event_id === ev.event_id);
          return (
            <li key={ev.event_id} className="rounded-2xl border border-black/10 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0"><p className="font-semibold">{ev.title}</p><p className="text-[13px] text-mute">{formatDay(ev.date.slice(0, 10))}{ev.time ? ` · ${formatTime(ev.time)}` : ""}{ev.location ? ` · ${ev.location}` : ""}</p><p className="text-[13px] text-mute">{rule(ev)}</p></div>
                {ev.open && members.length > 0 ? <Button size="sm" variant="outline" onClick={() => setForm(form?.event === ev.event_id && !form.entry ? null : { event: ev.event_id })}>Enter a {ev.is_team_event ? "team" : "person"}</Button> : <span className="text-[13px] text-mute">{ev.closed_reason}</span>}
              </div>
              {form?.event === ev.event_id && !form.entry && <EntryForm slug={slug} ev={ev} members={members} taken={takenIn(ev.event_id)} onDone={() => { setForm(null); load(); }} />}
              {mine.length > 0 && (
                <ul className="mt-3 space-y-2">
                  {mine.map((x) => (
                    <li key={x.id} className="rounded-xl bg-wash px-3 py-2.5 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span><Pill tone="green">Entered</Pill> <span className="ml-1">{x.members.map((m) => m.name).join(", ")}</span>{x.fee > 0 && <span className="text-mute"> · {inr(x.fee)}</span>}</span>
                        <span className="flex gap-3 text-[13px] font-semibold"><button onClick={() => setForm(form?.entry === x.id ? null : { event: ev.event_id, entry: x.id })} className="underline underline-offset-4">Change people</button><button disabled={busy} onClick={() => window.confirm(`Withdraw this entry from ${ev.title}?`) && run(() => api(`/api/fests/${slug}/entries/${x.id}`, { method: "DELETE" }))} className="text-red-600 hover:underline">Withdraw</button></span>
                      </div>
                      {x.warnings.map((w) => <p key={w} className="mt-1 text-[13px] text-amber-700">{w}</p>)}
                      {form?.entry === x.id && <EntryForm slug={slug} ev={ev} members={members} entry={x} taken={takenIn(ev.event_id, x.id)} onDone={() => { setForm(null); load(); }} />}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
      {d.entries.some((x) => x.status === "removed") && <div className="space-y-1">{d.entries.filter((x) => x.status === "removed").map((x) => <Notice key={x.id} tone="warn">The committee removed your entry in {x.event_title}.{x.note ? ` Reason: ${x.note}` : ""}</Notice>)}</div>}
    </section>
  );
}

// ─── accommodation ───────────────────────────────────────────────────────────

/** Asking for somewhere to stay, and seeing where the committee placed you. */
export function StayPortal({ slug }: { slug: string }) {
  const [d, setD] = useState<MyStay | null | undefined>(undefined);
  const [editing, setEditing] = useState(false);
  const [f, setF] = useState({ boys: "0", girls: "0", others: "0", arrival: "", departure: "", notes: "" });
  const load = useCallback(() => { api<MyStay | null>(`/api/fests/${slug}/accommodation/mine`).then((r) => { setD(r); const q = r?.request; if (q) setF({ boys: String(q.boys), girls: String(q.girls), others: String(q.others), arrival: q.arrival_date, departure: q.departure_date, notes: q.notes ?? "" }); }).catch(() => setD(null)); }, [slug]);
  useEffect(() => { load(); }, [load]);
  const { run, error, busy } = useRun(() => { setEditing(false); load(); });
  if (d === undefined) return <Skeleton className="h-24" />;
  if (!d || (!d.settings.enabled && !d.request)) return null;
  const r = d.request;
  const showForm = d.settings.open && (!r || r.status === "requested" || r.status === "declined") && (editing || !r || r.status === "declined");
  const submit = (e: React.FormEvent) => { e.preventDefault(); run(() => api(`/api/fests/${slug}/accommodation/mine`, { method: "PUT", body: { boys: Number(f.boys) || 0, girls: Number(f.girls) || 0, others: Number(f.others) || 0, arrival_date: f.arrival, departure_date: f.departure, notes: f.notes || null } })); };
  return (
    <section className="card space-y-4 p-6 sm:p-8" aria-label="Accommodation">
      <div><h3 className="font-display text-xl font-bold tracking-tight">Accommodation</h3>
        <p className="mt-1 text-sm text-mute">{d.settings.open ? `Tell the committee how many of you need a place to stay${d.settings.closes_on ? `, by ${formatDay(d.settings.closes_on)}` : ""}.` : r ? "" : "Requests for accommodation are closed."}</p></div>
      {r && r.status !== "declined" && (
        <div className="rounded-2xl bg-wash p-4 text-sm">
          <p className="flex flex-wrap items-center gap-2 font-semibold">{r.boys} boys · {r.girls} girls{r.others ? ` · ${r.others} others` : ""} <Pill tone={r.status === "allocated" ? "green" : "amber"}>{r.status === "allocated" ? "Places arranged" : "Waiting for the committee"}</Pill></p>
          <p className="text-mute">{formatDay(r.arrival_date)} to {formatDay(r.departure_date)} · {r.nights} night{r.nights === 1 ? "" : "s"}{r.notes ? ` · ${r.notes}` : ""}</p>
          {r.allocations.length > 0 && <ul className="mt-2 space-y-1">{r.allocations.map((a) => <li key={`${a.option_id}-${a.group}`}>{a.people} {a.group} in <strong>{a.option_name}</strong>{a.fee ? ` · ${inr(a.fee)}` : ""}</li>)}</ul>}
          {r.status === "allocated" && Object.values(r.unplaced).some((n) => n > 0) && <p className="mt-2 text-amber-700">Not everyone has a place yet. The committee will update this.</p>}
          <div className="mt-3 flex gap-4 font-semibold">{r.status === "requested" && d.settings.open && <button onClick={() => setEditing(!editing)} className="underline underline-offset-4">Change</button>}
            <button disabled={busy} onClick={() => window.confirm("Cancel your accommodation request?") && run(() => api(`/api/fests/${slug}/accommodation/mine`, { method: "DELETE" }))} className="text-red-600 hover:underline">Cancel request</button></div>
        </div>
      )}
      {r?.status === "declined" && <Notice tone="warn">The committee could not place you: {r.decision_note}. You can ask again below.</Notice>}
      {showForm && (
        <form onSubmit={submit} className="space-y-4">
          <ErrorNote>{error}</ErrorNote>
          <div className="grid gap-3 sm:grid-cols-3"><Field label="Boys"><input className="field" type="number" min={0} value={f.boys} onChange={(e) => setF({ ...f, boys: e.target.value })} /></Field><Field label="Girls"><input className="field" type="number" min={0} value={f.girls} onChange={(e) => setF({ ...f, girls: e.target.value })} /></Field><Field label="Others"><input className="field" type="number" min={0} value={f.others} onChange={(e) => setF({ ...f, others: e.target.value })} /></Field></div>
          <div className="grid gap-3 sm:grid-cols-2"><Field label="Arriving"><input className="field" type="date" required value={f.arrival} onChange={(e) => setF({ ...f, arrival: e.target.value })} /></Field><Field label="Leaving" hint="The morning you leave. Nights are counted from these dates."><input className="field" type="date" required min={f.arrival || undefined} value={f.departure} onChange={(e) => setF({ ...f, departure: e.target.value })} /></Field></div>
          <Field label="Anything the committee should know"><input className="field" maxLength={500} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
          <div className="flex gap-2"><Button type="submit" disabled={busy}>{r ? "Send again" : "Ask for accommodation"}</Button>{editing && <Button type="button" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>}</div>
        </form>
      )}
    </section>
  );
}

// ─── fees ────────────────────────────────────────────────────────────────────

const STATUS: Record<string, { text: string; tone: "green" | "amber" | "red" | "neutral" }> = { no_fees: { text: "Nothing to pay", tone: "neutral" }, unpaid: { text: "Unpaid", tone: "red" }, part: { text: "Part paid", tone: "amber" }, paid: { text: "Paid", tone: "green" }, overpaid: { text: "Paid, with extra", tone: "amber" } };

/** Pay all or part of what is owed, online. */
function FeePay({ contingentId, balance }: { contingentId: number; balance: number }) {
  const [amount, setAmount] = useState(String(balance));
  const value = Number(amount);
  const ok = value > 0 && value <= balance;
  return (
    <div className="space-y-3 rounded-2xl bg-wash p-4">
      <Field label="Amount to pay now (₹)" hint={`You can pay all ${inr(balance)} or part of it.`}><input className="field max-w-xs" type="number" min={1} max={balance} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
      <PayNow endpoint={`/api/payments/contingents/${contingentId}/checkout`} amount={value} body={{ amount: value }} label={ok ? `Pay ${inr(value)} online` : "Enter an amount to pay"} compact />
    </div>
  );
}

/** What the college owes, line by line, what has been received, and how to pay. */
export function FeesPortal({ slug }: { slug: string }) {
  const [st, setSt] = useState<FeeStatement | null | undefined>(undefined);
  useEffect(() => { api<FeeStatement | null>(`/api/fests/${slug}/fees/mine`).then(setSt).catch(() => setSt(null)); }, [slug]);
  const [payOn, setPayOn] = useState(false);
  useEffect(() => { api<PaymentConfig>("/api/payments/config").then((c) => setPayOn(c.enabled)).catch(() => {}); }, []);
  if (st === undefined) return <Skeleton className="h-24" />;
  if (!st || (st.lines.length === 0 && st.payments.length === 0)) return null;
  const s = STATUS[st.status];
  return (
    <section className="card space-y-4 p-6 sm:p-8" aria-label="Fees">
      <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-display text-xl font-bold tracking-tight">Your fees</h3><Pill tone={s.tone}>{s.text}</Pill></div>
      <table className="w-full text-sm"><tbody>
        {st.lines.map((l, i) => <tr key={i} className="border-b border-black/5"><td className="py-2">{l.label}{l.quantity > 1 && <span className="text-mute"> · {l.quantity} × {inr(l.unit)}</span>}</td><td className={`py-2 text-right ${l.amount < 0 ? "text-emerald-700" : ""}`}>{inr(l.amount)}</td></tr>)}
        <tr className="font-semibold"><td className="pt-3">Total</td><td className="pt-3 text-right">{inr(st.total)}</td></tr>
        {st.payments.map((p) => <tr key={p.id} className="text-emerald-700"><td className="pt-1">Received {formatDay(p.received_on)}{p.method ? ` · ${p.method}` : ""}</td><td className="pt-1 text-right">−{inr(p.amount)}</td></tr>)}
        <tr className="font-semibold"><td className="pt-3">{st.balance > 0 ? "Still to pay" : st.balance < 0 ? "Paid extra" : "Balance"}</td><td className={`pt-3 text-right ${st.balance > 0 ? "text-red-600" : ""}`}>{inr(Math.abs(st.balance))}</td></tr>
      </tbody></table>
      {st.balance > 0 && payOn && <FeePay contingentId={st.contingent_id} balance={st.balance} />}
      {st.balance > 0 && (st.due_on || st.instructions) && (
        <div className="rounded-2xl bg-wash p-4 text-sm">{st.due_on && <p className="font-semibold">Please pay by {formatDay(st.due_on)}.</p>}{st.instructions && <p className="mt-1 whitespace-pre-line">{st.instructions}</p>}</div>
      )}
      <p className="text-[13px] text-mute">This is worked out from your registration, your list, the events you entered and your accommodation, so it changes when they do.</p>
    </section>
  );
}
