"use client";

import { useCallback, useEffect, useState } from "react";
import { api, downloadFile } from "@/lib/api";
import type { AccomOption, AccomSettings, Contingent, ContingentDetail, EventEntry, FeeSettings, FeeStatement, FeeSummary, ManagedEvent, StayRequest } from "@/lib/types";
import { formatDay, formatTime, inr } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";

const label = (c: { name: string | null; college_name: string; leader_name?: string | null }) => c.name || (c.leader_name ? `${c.college_name} (${c.leader_name})` : c.college_name);

function useRun(after: () => void) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const run = useCallback(async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); after(); return true; } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); return false; } finally { setBusy(false); }
  }, [after]);
  return { run, error, busy };
}

// ─── event entries ───────────────────────────────────────────────────────────

function EnterForm({ slug, event, people, onDone }: { slug: string; event: ManagedEvent; people: Contingent[]; onDone: () => void }) {
  const [cid, setCid] = useState("");
  const [roster, setRoster] = useState<ContingentDetail["members"]>([]);
  const [picked, setPicked] = useState<number[]>([]);
  const { run, error, busy } = useRun(onDone);
  const choose = (id: string) => { setCid(id); setPicked([]); setRoster([]); if (id) api<ContingentDetail>(`/api/fests/${slug}/contingents/${id}`).then((d) => setRoster(d.members)).catch(() => {}); };
  const toggle = (id: number) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  return (
    <form onSubmit={(e) => { e.preventDefault(); run(() => api(`/api/fests/${slug}/entries`, { method: "POST", body: { event_id: event.id, contingent_id: Number(cid), member_ids: picked } })); }} className="mt-3 space-y-3 rounded-2xl bg-wash p-4">
      <ErrorNote>{error}</ErrorNote>
      <Field label="Enter on behalf of"><select className="field" required value={cid} onChange={(e) => choose(e.target.value)}><option value="">Choose a college</option>{people.map((c) => <option key={c.id} value={c.id}>{label(c)}</option>)}</select></Field>
      {roster.length > 0 && <div><p className="mb-1.5 text-[13px] font-semibold">{event.is_team_event ? `Who is on the team (${event.team_min ?? 1}–${event.team_max ?? "any"})` : "Who takes part (one person)"}</p>
        <div className="grid gap-1.5 sm:grid-cols-2">{roster.map((m) => <label key={m.id} className="flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-sm ring-1 ring-black/10"><input type="checkbox" checked={picked.includes(m.id)} onChange={() => toggle(m.id)} />{m.name}</label>)}</div></div>}
      {cid && roster.length === 0 && <p className="text-sm text-mute">This college has not added anyone to its list yet.</p>}
      <Button size="sm" type="submit" disabled={busy || !cid || picked.length === 0}>Add entry</Button>
    </form>
  );
}

/** Every event open to visiting colleges, with the entries it has received. The committee can enter or remove on a college's behalf. */
export function EntriesAdmin({ slug, people }: { slug: string; people: Contingent[] }) {
  const [events, setEvents] = useState<ManagedEvent[] | null>(null);
  const [entries, setEntries] = useState<EventEntry[]>([]);
  const [adding, setAdding] = useState<number | null>(null);
  const load = useCallback(() => {
    api<ManagedEvent[]>(`/api/fests/${slug}/manage/events`).then(setEvents).catch(() => setEvents([]));
    api<EventEntry[]>(`/api/fests/${slug}/entries`).then(setEntries).catch(() => {});
  }, [slug]);
  useEffect(() => { load(); }, [load]);
  const { run, error, busy } = useRun(load);
  if (!events) return <Skeleton className="h-40" />;
  const open = events.filter((e) => e.contingent_entries && !e.cancelled);
  if (open.length === 0) return <EmptyState title="No events are open to visiting colleges" body="Open an event to them under Events (the section “Can visiting colleges enter it?”) and choose how many entries each college may send and what an entry costs." />;
  return (
    <div className="max-w-4xl space-y-4">
      <p className="text-sm text-mute">Colleges enter from their own page. Here you can see every entry, enter a college yourself (even after the deadline) or remove one.</p>
      <ErrorNote>{error}</ErrorNote>
      {open.map((ev) => {
        const list = entries.filter((x) => x.event_id === ev.id && x.status === "confirmed");
        return (
          <article key={ev.id} className="card p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0"><h3 className="font-semibold">{ev.title}</h3>
                <p className="text-[13px] text-mute">{formatDay(ev.date.slice(0, 10))}{ev.time ? ` · ${formatTime(ev.time)}` : ""} · up to {ev.entries_per_contingent} per college · {ev.entry_fee ? `${inr(ev.entry_fee ?? 0)} ${ev.entry_fee_per === "participant" ? "each person" : "an entry"}` : "no entry fee"}{ev.entry_deadline ? ` · until ${formatDay(ev.entry_deadline)}` : ""}</p></div>
              <div className="flex items-center gap-3"><Pill tone="neutral">{list.length} entr{list.length === 1 ? "y" : "ies"} · {new Set(list.map((x) => x.contingent_id)).size} {new Set(list.map((x) => x.contingent_id)).size === 1 ? "college" : "colleges"}</Pill><button onClick={() => setAdding(adding === ev.id ? null : ev.id)} className="text-[13px] font-semibold underline underline-offset-4">{adding === ev.id ? "Close" : "Enter a college"}</button></div>
            </div>
            {list.length > 0 && (
              <ul className="mt-3 divide-y divide-[var(--ws-border)] rounded-xl bg-wash px-3 text-sm">
                {list.map((x) => (
                  <li key={x.id} className="flex flex-wrap items-start justify-between gap-2 py-2.5">
                    <span className="min-w-0"><span className="font-medium">{x.contingent_label}</span><span className="block text-[13px] text-mute">{x.members.map((m) => m.name + (m.phone ? ` (${m.phone})` : "")).join(", ")}</span>{x.warnings.map((w) => <span key={w} className="block text-[12px] text-amber-700">{w}</span>)}</span>
                    <button disabled={busy} onClick={() => { const why = window.prompt(`Remove ${x.contingent_label} from ${ev.title}? Say why (they will be told):`); if (why !== null) run(() => api(`/api/fests/${slug}/entries/${x.id}?reason=${encodeURIComponent(why)}`, { method: "DELETE" })); }} className="text-[13px] font-semibold text-red-600 hover:underline">Remove</button>
                  </li>
                ))}
              </ul>
            )}
            {adding === ev.id && <EnterForm slug={slug} event={ev} people={people} onDone={() => { setAdding(null); load(); }} />}
          </article>
        );
      })}
    </div>
  );
}

// ─── accommodation ───────────────────────────────────────────────────────────

function OptionForm({ slug, option, onDone }: { slug: string; option?: AccomOption; onDone: () => void }) {
  const [f, setF] = useState({ name: option?.name ?? "", description: option?.description ?? "", capacity: String(option?.capacity ?? ""), policy: option?.gender_policy ?? "any", fee: String(option?.fee_per_night ?? "") });
  const { run, error, busy } = useRun(onDone);
  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const body = { name: f.name, description: f.description || null, capacity: Number(f.capacity), gender_policy: f.policy, fee_per_night: Number(f.fee) || 0 };
    run(() => api(option ? `/api/fests/${slug}/accommodation/options/${option.id}` : `/api/fests/${slug}/accommodation/options`, { method: option ? "PATCH" : "POST", body }));
  };
  return (
    <form onSubmit={save} className="space-y-3 rounded-2xl bg-wash p-4">
      <ErrorNote>{error}</ErrorNote>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Name"><input className="field" required maxLength={120} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="e.g. Boys hostel, Block C" /></Field>
        <Field label="Holds (people)"><input className="field" type="number" required min={1} value={f.capacity} onChange={(e) => setF({ ...f, capacity: e.target.value })} /></Field>
        <Field label="For"><select className="field" value={f.policy} onChange={(e) => setF({ ...f, policy: e.target.value as "any" | "boys" | "girls" })}><option value="any">Anyone</option><option value="boys">Boys only</option><option value="girls">Girls only</option></select></Field>
        <Field label="Price per person per night (₹)" hint="0 if it is free"><input className="field" type="number" min={0} step="0.01" value={f.fee} onChange={(e) => setF({ ...f, fee: e.target.value })} /></Field>
      </div>
      <Field label="Details"><input className="field" maxLength={500} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} placeholder="Beds, bathrooms, distance from the venue" /></Field>
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy || !f.name.trim() || !f.capacity}>{option ? "Save" : "Add place"}</Button><Button size="sm" type="button" variant="ghost" onClick={onDone}>Cancel</Button></div>
    </form>
  );
}

function RequestCard({ slug, r, options, reload }: { slug: string; r: StayRequest; options: AccomOption[]; reload: () => void }) {
  const [placing, setPlacing] = useState(false);
  const [rows, setRows] = useState<{ option: string; group: string; people: string }[]>([]);
  const { run, error, busy } = useRun(() => { setPlacing(false); reload(); });
  const start = () => { setRows(r.allocations.length ? r.allocations.map((a) => ({ option: String(a.option_id), group: a.group, people: String(a.people) })) : [{ option: "", group: r.boys ? "boys" : r.girls ? "girls" : "others", people: "" }]); setPlacing(!placing); };
  const tone = r.status === "allocated" ? "green" : r.status === "declined" ? "red" : "amber";
  const save = (e: React.FormEvent) => { e.preventDefault(); run(() => api(`/api/fests/${slug}/accommodation/requests/${r.id}/allocations`, { method: "PUT", body: { allocations: rows.filter((x) => x.option && Number(x.people) > 0).map((x) => ({ option_id: Number(x.option), group: x.group, people: Number(x.people) })) } })); };
  const unplaced = Object.entries(r.unplaced).filter(([, n]) => n > 0).map(([g, n]) => `${n} ${g}`).join(", ");
  return (
    <article className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0"><h3 className="flex flex-wrap items-center gap-2 font-semibold">{r.contingent_label}<Pill tone={tone}>{r.status === "requested" ? "Waiting" : r.status === "allocated" ? "Placed" : "Declined"}</Pill></h3>
          <p className="text-[13px] text-mute">{r.boys} boys · {r.girls} girls{r.others ? ` · ${r.others} others` : ""} · {formatDay(r.arrival_date)} to {formatDay(r.departure_date)} ({r.nights} night{r.nights === 1 ? "" : "s"}){r.notes ? ` · ${r.notes}` : ""}</p></div>
        <div className="flex gap-3 text-[13px] font-semibold"><button onClick={start} className="underline underline-offset-4">{placing ? "Close" : r.allocations.length ? "Change places" : "Place them"}</button>
          {r.status !== "declined" && <button disabled={busy} onClick={() => { const why = window.prompt("Why can you not place them? They will be told."); if (why) run(() => api(`/api/fests/${slug}/accommodation/requests/${r.id}/decline`, { method: "POST", body: { note: why } })); }} className="text-red-600 hover:underline">Decline</button>}</div>
      </div>
      {r.allocations.length > 0 && <ul className="mt-2 space-y-1 text-sm">{r.allocations.map((a) => <li key={`${a.option_id}-${a.group}`}>{a.people} {a.group} in <strong>{a.option_name}</strong>{a.fee ? ` · ${inr(a.fee)}` : ""}</li>)}{unplaced && <li className="text-amber-700">Still no place for {unplaced}</li>}</ul>}
      {r.decision_note && <p className="mt-2 text-sm text-mute">Declined: {r.decision_note}</p>}
      {placing && (
        <form onSubmit={save} className="mt-3 space-y-3 rounded-2xl bg-wash p-4">
          <ErrorNote>{error}</ErrorNote>
          {rows.map((x, i) => (
            <div key={i} className="grid items-end gap-2 sm:grid-cols-[1fr_130px_100px_auto]">
              <Field label="Place"><select className="field" value={x.option} onChange={(e) => setRows(rows.map((y, j) => j === i ? { ...y, option: e.target.value } : y))}><option value="">Choose</option>{options.map((o) => <option key={o.id} value={o.id}>{o.name} ({o.free} free)</option>)}</select></Field>
              <Field label="Group"><select className="field" value={x.group} onChange={(e) => setRows(rows.map((y, j) => j === i ? { ...y, group: e.target.value } : y))}><option value="boys">Boys</option><option value="girls">Girls</option><option value="others">Others</option></select></Field>
              <Field label="People"><input className="field" type="number" min={1} value={x.people} onChange={(e) => setRows(rows.map((y, j) => j === i ? { ...y, people: e.target.value } : y))} /></Field>
              <button type="button" onClick={() => setRows(rows.filter((_, j) => j !== i))} className="pb-2 text-[13px] font-semibold text-red-600 hover:underline">Remove</button>
            </div>
          ))}
          <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy}>Save placing</Button><Button size="sm" type="button" variant="outline" onClick={() => setRows([...rows, { option: "", group: "boys", people: "" }])}>Add a row</Button></div>
        </form>
      )}
    </article>
  );
}

/** Accommodation: when colleges can ask, the places on offer and their price, and placing each request. */
export function StayAdmin({ slug }: { slug: string }) {
  const [settings, setSettings] = useState<AccomSettings | null>(null);
  const [options, setOptions] = useState<AccomOption[] | null>(null);
  const [requests, setRequests] = useState<StayRequest[]>([]);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [closes, setCloses] = useState("");
  const load = useCallback(() => {
    api<AccomSettings>(`/api/fests/${slug}/accommodation/settings`).then((s) => { setSettings(s); setCloses(s.closes_on ?? ""); });
    api<AccomOption[]>(`/api/fests/${slug}/accommodation/options`).then(setOptions).catch(() => setOptions([]));
    api<StayRequest[]>(`/api/fests/${slug}/accommodation/requests`).then(setRequests).catch(() => {});
  }, [slug]);
  useEffect(() => { load(); }, [load]);
  const { run, error, busy } = useRun(load);
  if (!settings || !options) return <Skeleton className="h-40" />;
  const put = (body: Record<string, unknown>) => run(() => api(`/api/fests/${slug}/accommodation/settings`, { method: "PUT", body }));
  return (
    <div className="max-w-4xl space-y-6">
      <ErrorNote>{error}</ErrorNote>
      <section className="card space-y-3 p-5" aria-label="Accommodation settings">
        <label className="flex items-start gap-3"><input type="checkbox" className="mt-1 h-4 w-4 accent-[#111]" checked={settings.enabled} disabled={busy} onChange={(e) => put({ enabled: e.target.checked })} /><span><span className="font-semibold">Let visiting colleges ask for accommodation</span><span className="block text-sm text-mute">They say how many boys, girls and others need a place, and which nights. You place them, and the cost is added to their fees.</span></span></label>
        {settings.enabled && <div className="flex flex-wrap items-end gap-3"><div className="w-48"><Field label="Requests close on" hint="Optional"><input className="field" type="date" value={closes} onChange={(e) => setCloses(e.target.value)} /></Field></div><Button size="sm" variant="outline" disabled={busy || closes === (settings.closes_on ?? "")} onClick={() => put({ closes_on: closes || null })}>Save date</Button></div>}
      </section>

      <section className="space-y-3" aria-label="Places to stay">
        <div className="flex items-center justify-between"><h2 className="text-[15px] font-semibold">Places to stay <span className="font-normal text-mute">{options.length}</span></h2><Button size="sm" variant="outline" onClick={() => setEditing(editing === "new" ? null : "new")}>{editing === "new" ? "Close" : "Add a place"}</Button></div>
        {editing === "new" && <OptionForm slug={slug} onDone={() => { setEditing(null); load(); }} />}
        {options.length === 0 && editing !== "new" ? <p className="text-sm text-mute">No places yet. Add the hostels and guest houses you can offer, with how many each holds and the price.</p> : (
          <ul className="space-y-2">{options.map((o) => (
            <li key={o.id} className="card p-4">
              {editing === o.id ? <OptionForm slug={slug} option={o} onDone={() => { setEditing(null); load(); }} /> : (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0"><p className="font-semibold">{o.name} <span className="ml-1 text-[12px] font-normal text-mute">{o.gender_policy === "any" ? "anyone" : `${o.gender_policy} only`}</span></p><p className="text-[13px] text-mute">{o.allocated} of {o.capacity} taken · {o.fee_per_night ? `${inr(o.fee_per_night)} per person per night` : "free"}{o.description ? ` · ${o.description}` : ""}</p></div>
                  <div className="flex gap-3 text-[13px] font-semibold"><button onClick={() => setEditing(o.id)} className="underline underline-offset-4">Edit</button><button disabled={busy} onClick={() => window.confirm(`Delete ${o.name}?`) && run(() => api(`/api/fests/${slug}/accommodation/options/${o.id}`, { method: "DELETE" }))} className="text-red-600 hover:underline">Delete</button></div>
                </div>
              )}
            </li>
          ))}</ul>
        )}
      </section>

      <section className="space-y-3" aria-label="Requests">
        <h2 className="text-[15px] font-semibold">Requests <span className="font-normal text-mute">{requests.length}</span></h2>
        {requests.length === 0 ? <p className="text-sm text-mute">{settings.enabled ? "Nobody has asked yet." : "Turn requests on above, and colleges can ask from their page."}</p> : requests.map((r) => <RequestCard key={r.id} slug={slug} r={r} options={options} reload={load} />)}
      </section>
    </div>
  );
}

// ─── fees ────────────────────────────────────────────────────────────────────

const STATUS: Record<string, { text: string; tone: "green" | "amber" | "red" | "neutral" }> = { no_fees: { text: "Nothing to pay", tone: "neutral" }, unpaid: { text: "Unpaid", tone: "red" }, part: { text: "Part paid", tone: "amber" }, paid: { text: "Paid", tone: "green" }, overpaid: { text: "Overpaid", tone: "amber" } };

function StatementCard({ slug, row, reload }: { slug: string; row: { contingent_id: number; contingent_label: string | null; total: number; paid: number; balance: number; status: string }; reload: () => void }) {
  const [open, setOpen] = useState(false);
  const [st, setSt] = useState<FeeStatement | null>(null);
  const [pay, setPay] = useState({ amount: "", method: "", reference: "" });
  const [adj, setAdj] = useState({ label: "", amount: "" });
  const refresh = useCallback(() => { api<FeeStatement>(`/api/fests/${slug}/fees/${row.contingent_id}`).then(setSt); reload(); }, [slug, row.contingent_id, reload]);
  const { run, error, busy } = useRun(refresh);
  const toggle = () => { setOpen(!open); if (!open && !st) api<FeeStatement>(`/api/fests/${slug}/fees/${row.contingent_id}`).then(setSt); };
  const s = STATUS[row.status] ?? STATUS.unpaid;
  const base = `/api/fests/${slug}/fees`;
  return (
    <li className="card p-4">
      <button onClick={toggle} className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 text-left" aria-expanded={open}>
        <span className="min-w-0 flex-1 font-semibold">{row.contingent_label}</span>
        <Pill tone={s.tone}>{s.text}</Pill>
        <span className="text-sm text-mute">{inr(row.paid)} of {inr(row.total)}</span>
        <span className={`w-24 text-right text-sm font-semibold ${row.balance > 0 ? "text-red-600" : ""}`}>{row.balance > 0 ? `${inr(row.balance)} due` : row.balance < 0 ? `${inr(-row.balance)} extra` : ""}</span>
      </button>
      {open && st && (
        <div className="mt-4 space-y-4 border-t border-[var(--ws-border)] pt-4">
          <ErrorNote>{error}</ErrorNote>
          <table className="w-full text-sm"><tbody>
            {st.lines.length === 0 && <tr><td className="py-1 text-mute">Nothing charged yet.</td></tr>}
            {st.lines.map((l, i) => <tr key={i} className="border-b border-black/5 last:border-0"><td className="py-1.5">{l.label}{l.quantity > 1 && <span className="text-mute"> · {l.quantity} × {inr(l.unit)}</span>}</td><td className={`py-1.5 text-right ${l.amount < 0 ? "text-emerald-700" : ""}`}>{inr(l.amount)}{l.adjustment_id && <button disabled={busy} onClick={() => run(() => api(`${base}/adjustments/${l.adjustment_id}`, { method: "DELETE" }))} className="ml-3 text-[12px] font-semibold text-red-600 hover:underline">Remove</button>}</td></tr>)}
            <tr className="font-semibold"><td className="pt-2">Total</td><td className="pt-2 text-right">{inr(st.total)}</td></tr>
          </tbody></table>
          {st.payments.length > 0 && <div><p className="mb-1 text-[13px] font-semibold">Received</p><ul className="space-y-1 text-sm">{st.payments.map((p) => <li key={p.id} className="flex justify-between gap-3"><span>{formatDay(p.received_on)}{p.method ? ` · ${p.method}` : ""}{p.reference ? ` · ${p.reference}` : ""}</span><span>{inr(p.amount)}<button disabled={busy} onClick={() => window.confirm("Delete this payment?") && run(() => api(`${base}/payments/${p.id}`, { method: "DELETE" }))} className="ml-3 text-[12px] font-semibold text-red-600 hover:underline">Delete</button></span></li>)}</ul></div>}
          <form onSubmit={(e) => { e.preventDefault(); run(() => api(`${base}/${row.contingent_id}/payments`, { method: "POST", body: { amount: Number(pay.amount), method: pay.method || null, reference: pay.reference || null } })).then((ok) => ok && setPay({ amount: "", method: "", reference: "" })); }} className="grid items-end gap-2 sm:grid-cols-[110px_1fr_1fr_auto]">
            <Field label="Payment received (₹)"><input className="field" type="number" min={0.01} step="0.01" required value={pay.amount} onChange={(e) => setPay({ ...pay, amount: e.target.value })} /></Field>
            <Field label="How"><input className="field" maxLength={40} value={pay.method} onChange={(e) => setPay({ ...pay, method: e.target.value })} placeholder="UPI, cash, cheque" /></Field>
            <Field label="Reference"><input className="field" maxLength={100} value={pay.reference} onChange={(e) => setPay({ ...pay, reference: e.target.value })} placeholder="Transaction id" /></Field>
            <Button size="sm" type="submit" disabled={busy || !pay.amount}>Record</Button>
          </form>
          <form onSubmit={(e) => { e.preventDefault(); run(() => api(`${base}/${row.contingent_id}/adjustments`, { method: "POST", body: { label: adj.label, amount: Number(adj.amount) } })).then((ok) => ok && setAdj({ label: "", amount: "" })); }} className="grid items-end gap-2 sm:grid-cols-[1fr_140px_auto]">
            <Field label="Add a line (late fee, waiver...)"><input className="field" minLength={2} maxLength={200} required value={adj.label} onChange={(e) => setAdj({ ...adj, label: e.target.value })} /></Field>
            <Field label="Amount (₹)" hint="Minus takes off"><input className="field" type="number" step="0.01" required value={adj.amount} onChange={(e) => setAdj({ ...adj, amount: e.target.value })} /></Field>
            <Button size="sm" variant="outline" type="submit" disabled={busy || !adj.label || !adj.amount}>Add</Button>
          </form>
        </div>
      )}
    </li>
  );
}

/** What the fest charges visiting colleges, who has paid, and the money received. */
export function FeesAdmin({ slug }: { slug: string }) {
  const [settings, setSettings] = useState<FeeSettings | null>(null);
  const [summary, setSummary] = useState<FeeSummary | null>(null);
  const [f, setF] = useState({ reg: "", member: "", due: "", how: "" });
  const [saved, setSaved] = useState(false);
  const load = useCallback(() => {
    api<FeeSettings>(`/api/fests/${slug}/fees/settings`).then((s) => { setSettings(s); setF({ reg: String(s.registration_fee), member: String(s.fee_per_member), due: s.fees_due_on ?? "", how: s.fee_instructions ?? "" }); });
    api<FeeSummary>(`/api/fests/${slug}/fees`).then(setSummary).catch(() => {});
  }, [slug]);
  useEffect(() => { load(); }, [load]);
  const refreshSummary = useCallback(() => { api<FeeSummary>(`/api/fests/${slug}/fees`).then(setSummary).catch(() => {}); }, [slug]);
  const { run, error, busy } = useRun(() => { setSaved(true); load(); });
  if (!settings || !summary) return <Skeleton className="h-40" />;
  const save = (e: React.FormEvent) => { e.preventDefault(); setSaved(false); run(() => api(`/api/fests/${slug}/fees/settings`, { method: "PUT", body: { registration_fee: Number(f.reg) || 0, fee_per_member: Number(f.member) || 0, fees_due_on: f.due || null, fee_instructions: f.how || null } })); };
  return (
    <div className="max-w-4xl space-y-6">
      <form onSubmit={save} className="card space-y-4 p-5" aria-label="Fees">
        <div><h2 className="text-[15px] font-semibold">What you charge visiting colleges</h2><p className="text-sm text-mute">Every fest is different. Leave a charge at 0 if you do not make it. Event entry fees are set on each event, and accommodation prices on each place.</p></div>
        <ErrorNote>{error}</ErrorNote>
        {saved && <Notice tone="ok">Saved.</Notice>}
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Registration fee (₹)" hint="Once for each team"><input className="field" type="number" min={0} step="0.01" value={f.reg} onChange={(e) => setF({ ...f, reg: e.target.value })} /></Field>
          <Field label="Fee for each person (₹)" hint="For everyone on its list"><input className="field" type="number" min={0} step="0.01" value={f.member} onChange={(e) => setF({ ...f, member: e.target.value })} /></Field>
          <Field label="Fees due by" hint="Optional"><input className="field" type="date" value={f.due} onChange={(e) => setF({ ...f, due: e.target.value })} /></Field>
        </div>
        <Field label="How to pay" hint="Shown to every college with its statement: bank details, a UPI id, who to contact."><textarea className="field min-h-20" maxLength={1000} value={f.how} onChange={(e) => setF({ ...f, how: e.target.value })} /></Field>
        <Button size="sm" type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</Button>
      </form>

      <section className="space-y-3" aria-label="Statements">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-[15px] font-semibold">Statements <span className="font-normal text-mute">{summary.rows.length}</span></h2>
          <div className="flex items-center gap-4 text-sm"><span>Due <strong>{inr(summary.total)}</strong></span><span>Received <strong>{inr(summary.paid)}</strong></span><span>Still to come <strong className={summary.balance > 0 ? "text-red-600" : ""}>{inr(summary.balance)}</strong></span>
            <Button size="sm" variant="outline" onClick={() => downloadFile(`/api/fests/${slug}/fees/export`, `${slug}-fees.csv`)}>Download CSV</Button></div>
        </div>
        {summary.rows.length === 0 ? <p className="text-sm text-mute">No approved colleges yet.</p> : <ul className="space-y-3">{summary.rows.map((r) => <StatementCard key={r.contingent_id} slug={slug} row={r} reload={refreshSummary} />)}</ul>}
      </section>
    </div>
  );
}
