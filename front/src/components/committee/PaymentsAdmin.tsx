"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PaymentConfig, PaymentList, PaymentRow } from "@/lib/types";
import { formatDay, inr } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";

const REFUND: Record<string, { text: string; tone: "green" | "amber" | "red" }> = { done: { text: "sent", tone: "green" }, pending: { text: "on its way", tone: "amber" }, failed: { text: "failed", tone: "red" } };

function Row({ slug, p, reload }: { slug: string; p: PaymentRow; reload: () => void }) {
  const [refunding, setRefunding] = useState(false);
  const [amount, setAmount] = useState(String(p.refundable));
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const call = async (path: string, body?: unknown) => {
    setBusy(true); setError("");
    try { await api(`/api/fests/${slug}/payments/${p.id}/${path}`, { method: "POST", body }); setRefunding(false); setReason(""); reload(); }
    catch (e) { setError(e instanceof Error ? e.message : "That did not work."); reload(); }
    finally { setBusy(false); }
  };
  const failed = p.refunds.some((r) => r.status === "failed") && p.refundable > 0;
  return (
    <li className="card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold">{p.event_title ?? p.description ?? "Payment"}{p.purpose === "contingent_fee" && <span className="ml-2 align-middle"><Pill tone="neutral">College fees</Pill></span>}</p>
          <p className="text-sm text-mute">{p.user_name} · {p.user_email}</p>
          <p className="text-[13px] text-mute">{p.paid_at ? `Paid ${formatDay(p.paid_at.slice(0, 10))}` : `Started ${formatDay(p.created_at.slice(0, 10))}`}{p.method ? ` · ${p.method.toUpperCase()}` : ""} · <span className="font-mono">{p.order_id}</span></p>
        </div>
        <div className="text-right"><p className="font-display text-xl font-bold">{inr(p.amount)}</p>{p.status !== "paid" && <Pill tone={p.status === "created" ? "amber" : "neutral"}>{p.status === "created" ? "Not finished" : p.status === "expired" ? "Expired" : "Failed"}</Pill>}</div>
      </div>
      {p.refunds.length > 0 && <ul className="mt-2 space-y-0.5 text-sm">{p.refunds.map((r) => <li key={r.id} className="flex flex-wrap items-center gap-2">Refund of {inr(r.amount)} <Pill tone={REFUND[r.status].tone}>{REFUND[r.status].text}</Pill><span className="text-mute">{r.reason}{r.status === "failed" && r.note ? `: ${r.note}` : ""}</span></li>)}</ul>}
      <ErrorNote>{error}</ErrorNote>
      {refunding ? (
        <div className="mt-3 space-y-3 rounded-2xl bg-wash p-4">
          <div className="grid gap-3 sm:grid-cols-[10rem_1fr]">
            <Field label="Amount (₹)" hint={`Up to ${inr(p.refundable)}`}><input className="field" type="number" min={1} max={p.refundable} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
            <Field label="Why" hint="The student is told"><input className="field" maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Charged twice" /></Field>
          </div>
          <div className="flex gap-2"><Button size="sm" disabled={busy || reason.trim().length < 3 || !(Number(amount) > 0)} onClick={() => window.confirm(`Send ${inr(Number(amount))} back to ${p.user_name}? This cannot be undone.`) && call("refund", { amount: Number(amount), reason: reason.trim() })}>Send the refund</Button><Button size="sm" variant="ghost" onClick={() => setRefunding(false)}>Cancel</Button></div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-4 text-[13px] font-semibold">
          {p.status === "paid" && p.purpose === "registration" && p.refundable > 0 && <button onClick={() => { setAmount(String(p.refundable)); setRefunding(true); }} className="underline underline-offset-4">{failed ? "Try the refund again" : "Refund"}</button>}
          {(p.status === "created" || p.refunds.some((r) => r.status === "pending")) && <button disabled={busy} onClick={() => call("refresh")} className="underline underline-offset-4">Check with the payment service</button>}
        </div>
      )}
    </li>
  );
}

/** Every payment made online to this fest: what came in, what went back, and the means to refund. */
export function PaymentsAdmin({ slug }: { slug: string }) {
  const [view, setView] = useState<"paid" | "created">("paid");
  const [data, setData] = useState<PaymentList | null>(null);
  const [cfg, setCfg] = useState<PaymentConfig | null>(null);
  const load = useCallback(() => { api<PaymentList>(`/api/fests/${slug}/payments?status=${view}`).then(setData).catch(() => setData({ collected: 0, refunded: 0, count: 0, payments: [] })); }, [slug, view]);
  useEffect(() => { setData(null); load(); }, [load]);
  useEffect(() => { api<PaymentConfig>("/api/payments/config").then(setCfg).catch(() => {}); }, []);
  return (
    <div className="max-w-4xl space-y-5">
      {cfg && !cfg.enabled && <Notice tone="warn">Online payment is not switched on for HiveOut yet, so paid events still confirm at once and no money moves.</Notice>}
      {cfg?.enabled && cfg.env === "sandbox" && <Notice tone="info">Online payment is in test mode: these are practice payments and no real money moves.</Notice>}
      {data && view === "paid" && data.count > 0 && (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="card p-4"><p className="text-sm text-mute">Collected online</p><p className="font-display text-3xl font-bold">{inr(data.collected)}</p><p className="text-[13px] text-mute">after refunds</p></div>
          <div className="card p-4"><p className="text-sm text-mute">Payments</p><p className="font-display text-3xl font-bold">{data.count}</p></div>
          <div className="card p-4"><p className="text-sm text-mute">Refunded</p><p className="font-display text-3xl font-bold">{inr(data.refunded)}</p></div>
        </div>
      )}
      <div className="flex gap-2" role="group" aria-label="Which payments">{([["paid", "Received"], ["created", "Not finished"]] as const).map(([id, label]) => <button key={id} aria-pressed={view === id} onClick={() => setView(id)} className={`rounded-full px-4 py-2 text-sm font-semibold transition ${view === id ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)] hover:text-ink"}`}>{label}</button>)}</div>
      {data === null ? <Skeleton className="h-32" /> : data.payments.length === 0 ? (
        <EmptyState title={view === "paid" ? "No online payments yet" : "Nothing waiting"} body={view === "paid" ? "When students pay for events, or visiting colleges pay their fees, online, each payment shows here. Money goes back from here too, and on its own when someone cancels in time." : "Payments that were started but never finished."} />
      ) : <ul className="space-y-3">{data.payments.map((p) => <Row key={p.id} slug={slug} p={p} reload={load} />)}</ul>}
      <p className="text-[13px] text-mute">Payments go to HiveOut&apos;s payment account first. Paying the money on to the fest is arranged outside HiveOut for now.</p>
    </div>
  );
}
