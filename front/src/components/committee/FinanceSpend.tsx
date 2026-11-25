"use client";

import { useCallback, useEffect, useState } from "react";
import { api, mediaSrc, uploadReceipt } from "@/lib/api";
import type { FinanceSettings, SpendOptions, SpendRequest, SpendStatus } from "@/lib/types";
import { formatDay, inr } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";

export function useRun(after: () => void) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const run = useCallback(async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); after(); return true; } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); return false; } finally { setBusy(false); }
  }, [after]);
  return { run, error, busy };
}

export const STATUS: Record<SpendStatus, { text: string; tone: "amber" | "green" | "red" | "neutral" }> = {
  pending: { text: "Waiting", tone: "amber" }, approved: { text: "Approved", tone: "green" }, paid: { text: "Paid", tone: "neutral" }, rejected: { text: "Not approved", tone: "red" }, cancelled: { text: "Withdrawn", tone: "neutral" },
};

/** Ask to spend money: what for, how much, a receipt, and whether you paid it yourself and need it back. */
export function SpendForm({ slug, options, settings, onDone, onCancel }: { slug: string; options: SpendOptions; settings: FinanceSettings | null; onDone: () => void; onCancel?: () => void }) {
  const [f, setF] = useState({ title: "", amount: "", where: "", spent_on: "", vendor: "", notes: "", mine: false });
  const [receipts, setReceipts] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const { run, error, busy } = useRun(onDone);
  const amount = Number(f.amount) || 0;
  const needReceipt = settings?.receipt_required_above != null && amount > settings.receipt_required_above;

  const addFile = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true); setUploadError("");
    try { const url = await uploadReceipt(slug, file); setReceipts((r) => [...r, url]); } catch (e) { setUploadError(e instanceof Error ? e.message : "Could not upload that file."); }
    setUploading(false);
  };
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const [kind, id] = f.where.split(":");
    run(() => api(`/api/fests/${slug}/finance/expenses`, { method: "POST", body: {
      title: f.title, amount, spent_on: f.spent_on || null, budget_line_id: kind === "line" ? Number(id) : null, category_id: kind === "cat" ? Number(id) : null,
      vendor: f.vendor || null, notes: f.notes || null, receipts, paid_by_me: f.mine,
    } }));
  };
  const small = settings && settings.auto_approve_below > 0 && amount > 0 && amount < settings.auto_approve_below;
  return (
    <form onSubmit={submit} className="card space-y-4 p-5">
      <h3 className="font-display text-lg font-semibold tracking-tight">Ask to spend money</h3>
      <ErrorNote>{error}</ErrorNote>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="What is it for?"><input className="field" required maxLength={200} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="e.g. Stage hire for two days" /></Field>
        <Field label="How much (₹)"><input className="field" type="number" required min={1} step="0.01" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} /></Field>
        <Field label="Which part of the budget?" hint="Pick a budget line, or just a category.">
          <select className="field" required value={f.where} onChange={(e) => setF({ ...f, where: e.target.value })}>
            <option value="">Choose</option>
            {options.lines.length > 0 && <optgroup label="Budget lines">{options.lines.map((l) => <option key={l.id} value={`line:${l.id}`}>{l.title} ({l.category_name}{l.team_name ? `, ${l.team_name}` : ""})</option>)}</optgroup>}
            <optgroup label="Categories">{options.categories.map((c) => <option key={c.id} value={`cat:${c.id}`}>{c.name}</option>)}</optgroup>
          </select>
        </Field>
        <Field label="Date"><input className="field" type="date" value={f.spent_on} onChange={(e) => setF({ ...f, spent_on: e.target.value })} /></Field>
        <Field label="Who is it paid to?"><input className="field" maxLength={120} value={f.vendor} onChange={(e) => setF({ ...f, vendor: e.target.value })} placeholder="Shop or person" /></Field>
        <Field label="Anything the committee should know"><input className="field" maxLength={500} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
      </div>
      <div>
        <p className="mb-1.5 text-sm font-semibold">Receipt or bill{needReceipt ? <span className="ml-1 font-normal text-red-700">(needed for more than {inr(settings!.receipt_required_above!)})</span> : <span className="ml-1 font-normal text-mute">(a photo or PDF)</span>}</p>
        <div className="flex flex-wrap items-center gap-3">
          {receipts.map((r, i) => <span key={r} className="inline-flex items-center gap-2 rounded-full bg-wash px-3 py-1.5 text-sm"><a href={mediaSrc(r) ?? "#"} target="_blank" rel="noopener noreferrer" className="font-semibold underline underline-offset-4">Receipt {i + 1}</a><button type="button" onClick={() => setReceipts(receipts.filter((x) => x !== r))} aria-label={`Remove receipt ${i + 1}`} className="text-red-600">×</button></span>)}
          {receipts.length < 5 && <label className="cursor-pointer rounded-full bg-white px-4 py-2 text-sm font-semibold shadow-[var(--shadow-card)] hover:bg-wash">{uploading ? "Uploading…" : "Add a file"}<input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" className="hidden" disabled={uploading} onChange={(e) => { addFile(e.target.files?.[0]); e.target.value = ""; }} /></label>}
        </div>
        {uploadError && <p role="alert" className="mt-1 text-sm text-red-700">{uploadError}</p>}
      </div>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={f.mine} onChange={(e) => setF({ ...f, mine: e.target.checked })} /><span><strong>I already paid this from my own pocket</strong><span className="block text-mute">The committee will see you are owed it back.</span></span></label>
      {small && <Notice tone="ok">This is under {inr(settings!.auto_approve_below)}, so it is approved straight away.</Notice>}
      <div className="flex gap-2"><Button type="submit" disabled={busy || uploading || !f.title.trim() || !amount || !f.where || (needReceipt && receipts.length === 0)}>{busy ? "Sending…" : "Send request"}</Button>{onCancel && <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>}</div>
    </form>
  );
}

function Receipts({ list }: { list: string[] }) {
  if (list.length === 0) return null;
  return <span className="inline-flex flex-wrap gap-2">{list.map((r, i) => <a key={r} href={mediaSrc(r) ?? "#"} target="_blank" rel="noopener noreferrer" className="text-[13px] font-semibold underline underline-offset-4">Receipt {i + 1}</a>)}</span>;
}

/** One request: what it is, its status and the people involved, and (for the committee) the buttons to decide it. */
export function SpendCard({ slug, e, staff, reload }: { slug: string; e: SpendRequest; staff: boolean; reload: () => void }) {
  const { run, error, busy } = useRun(reload);
  const s = STATUS[e.status];
  const base = `/api/fests/${slug}/finance/expenses/${e.id}`;
  return (
    <li className="card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 font-semibold">{e.title}<Pill tone={s.tone}>{s.text}</Pill>{e.auto_approved && <Pill tone="neutral">Approved automatically</Pill>}{e.out_of_pocket_by && e.status !== "paid" && <Pill tone="amber">Owed to {e.out_of_pocket_by}</Pill>}</p>
          <p className="text-[13px] text-mute">{e.line_title ?? e.category_name} · {formatDay(e.spent_on)}{e.vendor ? ` · ${e.vendor}` : ""}{staff && e.requested_by_name ? ` · asked by ${e.requested_by_name}` : ""}</p>
          {e.notes && <p className="mt-1 text-sm">{e.notes}</p>}
          <div className="mt-1"><Receipts list={e.receipts} /></div>
          {e.decision_note && <p className="mt-1 text-[13px] text-mute">{e.status === "rejected" ? "Why not: " : "Note: "}{e.decision_note}{e.decided_by_name ? ` (${e.decided_by_name})` : ""}</p>}
          {e.status === "paid" && <p className="mt-1 text-[13px] text-mute">{e.out_of_pocket_by ? "Paid back" : "Paid"} on {e.paid_on ? formatDay(e.paid_on) : ""}{e.paid_note ? ` · ${e.paid_note}` : ""}</p>}
        </div>
        <p className="shrink-0 text-lg font-semibold">{inr(e.amount)}</p>
      </div>
      <ErrorNote>{error}</ErrorNote>
      <div className="mt-3 flex flex-wrap gap-2">
        {staff && e.status === "pending" && <>
          <Button size="sm" disabled={busy} onClick={() => run(() => api(`${base}/approve`, { method: "POST", body: {} }))}>Approve</Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => { const why = window.prompt("Why not? The person who asked will see this."); if (why) run(() => api(`${base}/reject`, { method: "POST", body: { note: why } })); }}>Turn down</Button>
        </>}
        {staff && e.status === "approved" && <Button size="sm" disabled={busy} onClick={() => { const how = window.prompt(e.out_of_pocket_by ? `How did you pay ${e.out_of_pocket_by} back? (optional)` : "How was it paid? (optional, e.g. UPI reference)"); if (how !== null) run(() => api(`${base}/pay`, { method: "POST", body: { note: how || null } })); }}>{e.out_of_pocket_by ? "Mark as paid back" : "Mark as paid"}</Button>}
        {e.status === "pending" && <Button size="sm" variant="ghost" disabled={busy} onClick={() => window.confirm("Withdraw this request?") && run(() => api(`${base}/cancel`, { method: "POST" }))}>Withdraw</Button>}
        {staff && e.status !== "paid" && <button disabled={busy} onClick={() => window.confirm("Delete this request?") && run(() => api(base, { method: "DELETE" }))} className="px-2 text-[13px] font-semibold text-red-600 hover:underline">Delete</button>}
      </div>
    </li>
  );
}

/** What anyone on the committee sees: ask to spend money, and follow their own requests. */
export function MySpendPanel({ slug }: { slug: string }) {
  const [options, setOptions] = useState<SpendOptions | null>(null);
  const [settings, setSettings] = useState<FinanceSettings | null>(null);
  const [list, setList] = useState<SpendRequest[] | null>(null);
  const [asking, setAsking] = useState(false);
  const load = useCallback(() => {
    api<SpendRequest[]>(`/api/fests/${slug}/finance/expenses`).then(setList).catch(() => setList([]));
  }, [slug]);
  useEffect(() => {
    load();
    api<SpendOptions>(`/api/fests/${slug}/finance/options`).then(setOptions).catch(() => {});
    api<FinanceSettings>(`/api/fests/${slug}/finance/settings`).then(setSettings).catch(() => {});
  }, [slug, load]);
  if (!list || !options) return <Skeleton className="h-24" />;
  return (
    <section className="mb-8 space-y-4" aria-label="Spend requests">
      <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-display text-lg font-semibold tracking-tight">Money you have asked for</h2><Button size="sm" variant="outline" onClick={() => setAsking(!asking)}>{asking ? "Close" : "Ask to spend money"}</Button></div>
      {asking && <SpendForm slug={slug} options={options} settings={settings} onCancel={() => setAsking(false)} onDone={() => { setAsking(false); load(); }} />}
      {list.length === 0 ? <p className="text-sm text-mute">Nothing yet. If you need money for something for the fest, ask here and the committee will decide.</p> : <ul className="space-y-3">{list.map((e) => <SpendCard key={e.id} slug={slug} e={e} staff={false} reload={load} />)}</ul>}
    </section>
  );
}

const FILTERS: { id: SpendStatus | "all"; label: string }[] = [{ id: "pending", label: "Waiting" }, { id: "approved", label: "To pay" }, { id: "paid", label: "Paid" }, { id: "rejected", label: "Not approved" }, { id: "all", label: "All" }];

/** Every request, for the committee to decide, pay and look back on. */
export function SpendingPanel({ slug, onChanged }: { slug: string; onChanged: () => void }) {
  const [list, setList] = useState<SpendRequest[] | null>(null);
  const [options, setOptions] = useState<SpendOptions | null>(null);
  const [settings, setSettings] = useState<FinanceSettings | null>(null);
  const [filter, setFilter] = useState<SpendStatus | "all">("pending");
  const [asking, setAsking] = useState(false);
  const load = useCallback(() => { api<SpendRequest[]>(`/api/fests/${slug}/finance/expenses`).then(setList).catch(() => setList([])); onChanged(); }, [slug, onChanged]);
  useEffect(() => {
    load();
    api<SpendOptions>(`/api/fests/${slug}/finance/options`).then(setOptions).catch(() => {});
    api<FinanceSettings>(`/api/fests/${slug}/finance/settings`).then(setSettings).catch(() => {});
  }, [slug]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!list || !options) return <Skeleton className="h-40" />;
  const count = (id: SpendStatus | "all") => list.filter((e) => id === "all" ? e.status !== "cancelled" : e.status === id).length;
  const shown = list.filter((e) => (filter === "all" ? e.status !== "cancelled" : e.status === filter));
  return (
    <div className="max-w-4xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter requests">
          {FILTERS.map((x) => <button key={x.id} aria-pressed={filter === x.id} onClick={() => setFilter(x.id)} className={`rounded-full px-4 py-2 text-sm font-semibold transition ${filter === x.id ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)] hover:text-ink"}`}>{x.label} <span className="font-normal opacity-70">({count(x.id)})</span></button>)}
        </div>
        <Button size="sm" onClick={() => setAsking(!asking)}>{asking ? "Close" : "New request"}</Button>
      </div>
      {asking && <SpendForm slug={slug} options={options} settings={settings} onCancel={() => setAsking(false)} onDone={() => { setAsking(false); load(); }} />}
      {shown.length === 0 ? <EmptyState title={filter === "pending" ? "Nothing is waiting" : "Nothing here"} body={filter === "pending" ? "When someone on the committee asks to spend money, it shows up here for you to approve or turn down." : "Try another filter."} /> : <ul className="space-y-3">{shown.map((e) => <SpendCard key={e.id} slug={slug} e={e} staff reload={load} />)}</ul>}
    </div>
  );
}
