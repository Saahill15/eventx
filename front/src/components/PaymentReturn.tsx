"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import type { PaymentResult } from "@/lib/types";
import { inr } from "@/lib/format";
import { Button } from "./ui/Button";
import { ErrorNote, Skeleton } from "./ui/bits";

/** Where the payment page sends people back to. We ask the server (which asks the gateway) what became of the order, a few times if it is still settling. */
export function PaymentReturn() {
  const orderId = useSearchParams().get("order_id");
  const [r, setR] = useState<PaymentResult | null>(null);
  const [error, setError] = useState("");
  const [tries, setTries] = useState(0);
  useEffect(() => {
    if (!orderId) return;
    let stop = false;
    const check = async (n: number) => {
      try {
        const res = await api<PaymentResult>(`/api/payments/orders/${encodeURIComponent(orderId)}/verify`, { method: "POST" });
        if (stop) return;
        setR(res); setTries(n);
        if (res.status === "created" && n < 6) window.setTimeout(() => check(n + 1), 3000);
      } catch (e) { if (!stop) setError(e instanceof Error ? e.message : "Could not check your payment."); }
    };
    check(1);
    return () => { stop = true; };
  }, [orderId]);

  if (!orderId) return <ErrorNote>This page needs a payment reference.</ErrorNote>;
  if (error) return <div className="space-y-4"><ErrorNote>{error}</ErrorNote><Button href="/my-passes" variant="outline">My passes</Button></div>;
  if (!r) return <Skeleton className="h-48" />;
  const done = r.status === "paid";
  const waiting = r.status === "created";
  const where = r.purpose === "registration" ? (r.event_id ? `/events/${r.event_id}` : "/my-passes") : r.fest_slug ? `/fests/${r.fest_slug}/contingent` : "/my-passes";
  return (
    <div className="card space-y-4 p-8 text-center" role="status" aria-live="polite">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-wash">
        {done ? <CheckCircle2 className="h-8 w-8 text-emerald-600" /> : waiting ? <Clock className="h-8 w-8 text-chip-ink" /> : <XCircle className="h-8 w-8 text-red-600" />}
      </div>
      <h1 className="font-display text-3xl font-bold tracking-tight">{done ? "Payment received" : waiting ? "Waiting for your bank" : "The payment did not go through"}</h1>
      <p className="text-mute">
        {done ? `${inr(r.amount)} for ${r.event_title ?? r.description ?? "your payment"}. ${r.purpose === "registration" ? "You are registered." : "It is on your statement."}` : waiting ? (tries >= 6 ? "Your bank has not confirmed yet. If money left your account it will be sorted out on its own, and refunded if the seat has gone. You can check again in a few minutes." : "Hold on while we check. This can take a few seconds.") : "No money was taken, or it will be returned to you by your bank. Your seat is held for a short while: you can try again from the event page."}
      </p>
      <div className="flex flex-wrap justify-center gap-3">
        <Button href={where}>{done || waiting ? (r.purpose === "registration" ? "See the event" : "Back to my college") : "Try again"}</Button>
        <Button href="/my-passes" variant="outline">My passes</Button>
      </div>
      {waiting && tries >= 6 && <Link href={`/payments/return?order_id=${orderId}`} className="block text-sm font-semibold underline underline-offset-4" onClick={() => window.location.reload()}>Check again</Link>}
    </div>
  );
}
