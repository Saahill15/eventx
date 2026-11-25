"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatDay, inr } from "@/lib/format";
import type { FestEvent, Quote, Tier } from "@/lib/types";
import { Field } from "./ui/bits";

const WHY: Record<string, string> = { not_yet: "Not on sale yet", ended: "Sale ended", sold_out: "Sold out", off: "Not available" };

/**
 * Choosing a ticket and entering a promo code, with the price you will pay worked out by the server as you go.
 * Shown only for events that cost something or sell more than one kind of ticket.
 */
export function TicketPicker({ event, verified, tierId, setTierId, promo, setPromo, onQuote, onTiers }: {
  event: FestEvent; verified: boolean; tierId: number | null; setTierId: (id: number | null) => void; promo: string; setPromo: (c: string) => void;
  onQuote: (q: Quote | null) => void; onTiers: (count: number) => void;
}) {
  const [tiers, setTiers] = useState<Tier[] | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [problem, setProblem] = useState("");
  const [checking, setChecking] = useState(false);

  useEffect(() => { api<Tier[]>(`/api/events/${event.id}/tiers`).then((t) => { setTiers(t); onTiers(t.length); if (t.length === 1 && t[0].status === "on_sale") setTierId(t[0].id); }).catch(() => { setTiers([]); onTiers(0); }); }, [event.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const needsTier = (tiers?.length ?? 0) > 0;
  const priced = event.is_paid || needsTier;
  // Work the price out whenever the choice or the code changes (the code is checked when they stop typing)
  useEffect(() => {
    if (tiers === null || !priced || (needsTier && tierId === null)) { setQuote(null); onQuote(null); setProblem(""); return; }
    let live = true;
    setChecking(true);
    const timer = window.setTimeout(() => {
      api<Quote>(`/api/fest-events/${event.id}/quote`, { method: "POST", body: { ticket_tier_id: tierId, promo_code: promo.trim() || null } })
        .then((q) => { if (live) { setQuote(q); onQuote(q); setProblem(""); } })
        .catch((e) => { if (live) { setQuote(null); onQuote(null); setProblem(e instanceof Error ? e.message : "That did not work."); } })
        .finally(() => live && setChecking(false));
    }, promo.trim() ? 450 : 0);
    return () => { live = false; window.clearTimeout(timer); };
  }, [tiers, tierId, promo, priced, needsTier, event.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (tiers === null || !priced) return null;
  return (
    <div className="space-y-4">
      {needsTier && (
        <fieldset className="space-y-2">
          <legend className="mb-1 text-sm font-semibold">Choose your ticket</legend>
          {tiers.map((t) => {
            const price = verified && t.student_price !== null ? t.student_price : t.price;
            const on = t.status === "on_sale";
            return (
              <label key={t.id} className={`flex cursor-pointer items-start gap-3 rounded-2xl p-3.5 ring-1 transition ${tierId === t.id ? "bg-white ring-2 ring-ink" : "bg-white/60 ring-black/10"} ${on ? "" : "cursor-not-allowed opacity-60"}`}>
                <input type="radio" name="ticket" className="mt-1" checked={tierId === t.id} disabled={!on} onChange={() => setTierId(t.id)} />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-baseline justify-between gap-2"><span className="font-semibold">{t.name}</span><span className="font-semibold">{price === 0 ? "Free" : inr(price)}{verified && t.student_price !== null && <span className="ml-1 text-xs font-normal text-mute line-through">{inr(t.price)}</span>}</span></span>
                  {t.description && <span className="block text-sm text-mute">{t.description}</span>}
                  <span className="block text-xs text-mute">{on ? (t.remaining !== null ? `${t.remaining} left` : "") : WHY[t.status]}{t.status === "not_yet" && t.sales_open_on ? ` · from ${formatDay(t.sales_open_on)}` : ""}{on && t.sales_close_on ? `${t.remaining !== null ? " · " : ""}sale ends ${formatDay(t.sales_close_on)}` : ""}</span>
                </span>
              </label>
            );
          })}
        </fieldset>
      )}
      {(event.is_paid || tiers.some((t) => t.price > 0)) && (
        <Field label="Promo code" hint="Optional">
          <input className="field uppercase" maxLength={40} value={promo} onChange={(e) => setPromo(e.target.value)} placeholder="Have a code?" autoComplete="off" />
        </Field>
      )}
      {problem && promo.trim() && <p role="alert" className="text-sm text-red-700">{problem}</p>}
      {quote && (
        <p className="rounded-2xl bg-wash px-4 py-3 text-sm" aria-live="polite">
          {quote.discount > 0 ? <><span className="text-mute line-through">{inr(quote.price)}</span> <strong>{quote.total === 0 ? "Free" : inr(quote.total)}</strong> <span className="text-emerald-700">· you save {inr(quote.discount)}{quote.promo_description ? ` with ${promo.trim().toUpperCase()}` : ""}</span></> : <>You pay <strong>{quote.total === 0 ? "nothing: it is free" : inr(quote.total)}</strong></>}
        </p>
      )}
      {checking && !quote && !problem && <p className="text-xs text-mute">Working out the price…</p>}
    </div>
  );
}
