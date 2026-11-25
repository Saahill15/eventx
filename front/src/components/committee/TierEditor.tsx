"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Tier } from "@/lib/types";
import { formatDay, inr } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Field, Pill } from "@/components/ui/bits";

const STATUS: Record<string, { text: string; tone: "green" | "amber" | "red" | "neutral" }> = {
  on_sale: { text: "On sale", tone: "green" }, not_yet: { text: "Not on sale yet", tone: "amber" }, ended: { text: "Sale ended", tone: "neutral" }, sold_out: { text: "Sold out", tone: "red" }, off: { text: "Switched off", tone: "neutral" },
};

function TierForm({ eventId, tier, onDone }: { eventId: number; tier?: Tier; onDone: () => void }) {
  const [f, setF] = useState({ name: tier?.name ?? "", description: tier?.description ?? "", price: tier ? String(tier.price) : "", student: tier?.student_price != null ? String(tier.student_price) : "", quantity: tier?.quantity != null ? String(tier.quantity) : "", opens: tier?.sales_open_on ?? "", closes: tier?.sales_close_on ?? "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    const body = { name: f.name, description: f.description || null, price: Number(f.price) || 0, student_price: f.student === "" ? null : Number(f.student), quantity: f.quantity === "" ? null : Number(f.quantity), sales_open_on: f.opens || null, sales_close_on: f.closes || null };
    try { await api(tier ? `/api/ticket-tiers/${tier.id}` : `/api/events/${eventId}/tiers`, { method: tier ? "PATCH" : "POST", body }); onDone(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not save."); setBusy(false); }
  };
  return (
    <div className="space-y-3 rounded-2xl bg-white p-4 ring-1 ring-black/10">
      <ErrorNote>{error}</ErrorNote>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Name"><input className="field" required maxLength={80} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="e.g. Early bird" /></Field>
        <Field label="Price (₹)" hint="0 for a free ticket"><input className="field" type="number" min={0} step="0.01" required value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} /></Field>
        <Field label="Student price (₹)" hint="Optional. Lower than the price, for verified students."><input className="field" type="number" min={0} step="0.01" value={f.student} onChange={(e) => setF({ ...f, student: e.target.value })} /></Field>
        <Field label="How many of this ticket" hint="Leave empty for no limit"><input className="field" type="number" min={1} value={f.quantity} onChange={(e) => setF({ ...f, quantity: e.target.value })} /></Field>
        <Field label="On sale from" hint="Optional"><input className="field" type="date" value={f.opens} onChange={(e) => setF({ ...f, opens: e.target.value })} /></Field>
        <Field label="On sale until" hint="Optional"><input className="field" type="date" min={f.opens || undefined} value={f.closes} onChange={(e) => setF({ ...f, closes: e.target.value })} /></Field>
      </div>
      <Field label="What it includes"><input className="field" maxLength={300} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} placeholder="e.g. Front-row seat and a free drink" /></Field>
      <div className="flex gap-2"><Button size="sm" type="button" disabled={busy || !f.name.trim() || f.price === ""} onClick={save}>{tier ? "Save" : "Add ticket"}</Button><Button size="sm" type="button" variant="ghost" onClick={onDone}>Cancel</Button></div>
    </div>
  );
}

/**
 * The kinds of ticket an event sells (Early bird, Regular, VIP), each with its own price, student price, number of seats and sale dates.
 * Only for events that already exist, since tickets belong to an event. With none, the event simply has one price.
 */
export function TierEditor({ eventId, onCount }: { eventId: number | null; onCount: (n: number) => void }) {
  const [tiers, setTiers] = useState<Tier[] | null>(null);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => { if (eventId) api<Tier[]>(`/api/events/${eventId}/tiers`).then((t) => { setTiers(t); onCount(t.length); }).catch(() => setTiers([])); }, [eventId, onCount]);
  useEffect(() => { load(); }, [load]);
  const act = async (fn: () => Promise<unknown>) => { setError(""); try { await fn(); load(); } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); } };

  if (!eventId) return <p className="rounded-2xl bg-wash px-4 py-3 text-sm text-mute">Want more than one kind of ticket (early bird, VIP)? Save the event first, then edit it to add them.</p>;
  if (!tiers) return null;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-sm font-semibold">Different tickets <span className="font-normal text-mute">(optional)</span></p><p className="text-sm text-mute">Early bird, regular, VIP. Once you add one, people choose a ticket and the price comes from it.</p></div>
        <Button size="sm" type="button" variant="outline" onClick={() => setEditing(editing === "new" ? null : "new")}>{editing === "new" ? "Close" : "Add a ticket"}</Button></div>
      <ErrorNote>{error}</ErrorNote>
      {editing === "new" && <TierForm eventId={eventId} onDone={() => { setEditing(null); load(); }} />}
      <ul className="space-y-2">
        {tiers.map((t) => (
          <li key={t.id}>
            {editing === t.id ? <TierForm eventId={eventId} tier={t} onDone={() => { setEditing(null); load(); }} /> : (
              <div className="rounded-2xl bg-white px-4 py-3 ring-1 ring-black/10">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="flex flex-wrap items-center gap-2 font-semibold">{t.name}<Pill tone={STATUS[t.status].tone}>{STATUS[t.status].text}</Pill></p>
                  <p className="font-semibold">{t.price === 0 ? "Free" : inr(t.price)}{t.student_price !== null && <span className="ml-2 text-sm font-normal text-mute">students {inr(t.student_price)}</span>}</p>
                </div>
                <p className="text-[13px] text-mute">{t.sold ?? 0} sold{t.quantity !== null ? ` of ${t.quantity}` : ""}{t.sales_open_on ? ` · from ${formatDay(t.sales_open_on)}` : ""}{t.sales_close_on ? ` · until ${formatDay(t.sales_close_on)}` : ""}{t.description ? ` · ${t.description}` : ""}</p>
                <div className="mt-2 flex gap-4 text-[13px] font-semibold">
                  <button type="button" onClick={() => setEditing(t.id)} className="underline underline-offset-4">Edit</button>
                  <button type="button" onClick={() => act(() => api(`/api/ticket-tiers/${t.id}`, { method: "PATCH", body: { active: !t.active } }))} className="underline underline-offset-4">{t.active ? "Switch off" : "Switch on"}</button>
                  <button type="button" onClick={() => window.confirm(`Delete “${t.name}”?`) && act(() => api(`/api/ticket-tiers/${t.id}`, { method: "DELETE" }))} className="text-red-600 hover:underline">Delete</button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
