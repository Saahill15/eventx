"use client";

import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { openCheckout } from "@/lib/payments";
import type { Checkout } from "@/lib/types";
import { inr } from "@/lib/format";
import { Button } from "./ui/Button";
import { ErrorNote, Field } from "./ui/bits";

const minutesLeft = (iso: string | null | undefined) => (iso ? Math.max(0, Math.round((new Date(iso.endsWith("Z") ? iso : `${iso}Z`).getTime() - Date.now()) / 60000)) : null);

/**
 * Pay online for something: a registration that holds a seat, or a college's fees. Asks for a mobile number the first time
 * (the payment service needs one for the receipt), then opens the gateway's page.
 */
export function PayNow({ endpoint, amount, label, holdUntil, body = {}, compact = false }: { endpoint: string; amount: number; label?: string; holdUntil?: string | null; body?: Record<string, unknown>; compact?: boolean }) {
  const { user } = useAuth();
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [left, setLeft] = useState(minutesLeft(holdUntil));
  useEffect(() => { setLeft(minutesLeft(holdUntil)); const t = window.setInterval(() => setLeft(minutesLeft(holdUntil)), 20000); return () => window.clearInterval(t); }, [holdUntil]);
  const needsPhone = !user?.phone;
  const pay = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const c = await api<Checkout>(endpoint, { method: "POST", body: { ...body, ...(phone.trim() ? { phone: phone.trim() } : {}) } });
      await openCheckout(c);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not start the payment."); setBusy(false); }
  };
  return (
    <form onSubmit={pay} className={compact ? "space-y-2" : "space-y-3 rounded-2xl bg-wash p-4"}>
      {!compact && left !== null && <p className="flex items-center gap-2 text-sm font-semibold"><Clock className="h-4 w-4" />{left > 0 ? `Your seat is held for ${left} more minute${left === 1 ? "" : "s"}. Pay to keep it.` : "Your seat hold is about to run out. Pay now to keep it."}</p>}
      {needsPhone && <Field label="Mobile number" hint="For the payment receipt. We do not save it."><input className="field" inputMode="numeric" required maxLength={20} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="98765 43210" /></Field>}
      <ErrorNote>{error}</ErrorNote>
      <Button type="submit" disabled={busy} className={compact ? "" : "w-full"}>{busy ? "Opening the payment page…" : label ?? `Pay ${inr(amount)}`}</Button>
    </form>
  );
}
