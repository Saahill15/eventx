"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Clock, Ticket, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { CityPass, FestEvent, FestPass, Registration } from "@/lib/types";
import { Button } from "./ui/Button";
import { ErrorNote } from "./ui/bits";

type State = "unknown" | "none" | "confirmed" | "waiting" | "rejected";

export function RegisterPanel({ event, hasEnded }: { event: FestEvent; hasEnded: boolean }) {
  const { user, loading } = useAuth();
  const [state, setState] = useState<State>("unknown");
  const [hasFestPass, setHasFestPass] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const isFest = event.event_type === "fest";
  const needsRegistration = isFest && event.requires_registration;
  const next = encodeURIComponent(`/events/${event.id}`);

  const refresh = useCallback(async () => {
    try {
      if (needsRegistration) {
        const regs = await api<Registration[]>("/api/fest-events/my-registrations");
        const mine = regs.find((r) => r.event_id === event.id);
        setState(!mine ? "none" : mine.approval_status === "approved" ? "confirmed" : mine.approval_status === "pending" ? "waiting" : "rejected");
      } else if (isFest) {
        await api<FestPass>(`/api/fests/${event.fest_slug}/my-pass`).then(() => setHasFestPass(true)).catch(() => setHasFestPass(false));
        setState("none");
      } else {
        const passes = await api<CityPass[]>("/api/passes/my");
        setState(passes.some((p) => p.event_id === event.id) ? "confirmed" : "none");
      }
    } catch { setState("none"); }
  }, [event.id, event.fest_slug, isFest, needsRegistration]);

  useEffect(() => { if (user) refresh(); }, [user, refresh]);

  const act = async () => {
    setBusy(true); setError("");
    try {
      if (needsRegistration) {
        await api(`/api/fests/${event.fest_slug}/entry-pass`, { method: "POST" });
        await api(`/api/fest-events/${event.id}/register`, { method: "POST" });
      } else if (isFest) await api(`/api/fests/${event.fest_slug}/entry-pass`, { method: "POST" });
      else await api(`/api/passes/${event.id}/register`, { method: "POST" });
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  };

  if (hasEnded) return <p className="rounded-2xl bg-wash px-4 py-4 text-center text-sm font-semibold text-mute">This event has already taken place.</p>;
  if (loading) return <div className="h-14 animate-pulse rounded-full bg-wash" />;

  if (!user) {
    return (
      <div className="space-y-3">
        <Button href={`/login?next=${next}`} size="lg" className="w-full">Sign in to {needsRegistration || !isFest ? "register" : "get your pass"}</Button>
        <p className="text-center text-sm text-mute">New here? <Link href={`/signup?next=${next}`} className="font-semibold text-ink underline underline-offset-4">Create a free account</Link></p>
      </div>
    );
  }

  const done = (icon: React.ReactNode, title: string, body?: string) => (
    <motion.div initial={{ opacity: 0, scale: 0.94 }} animate={{ opacity: 1, scale: 1 }} transition={{ type: "spring", stiffness: 300, damping: 20 }} className="rounded-2xl bg-wash p-4">
      <p className="flex items-center gap-2 font-semibold"><motion.span initial={{ scale: 0, rotate: -30 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: "spring", stiffness: 400, damping: 14, delay: 0.1 }} className="inline-flex">{icon}</motion.span>{title}</p>
      {body && <p className="mt-1 text-sm text-mute">{body}</p>}
      <Link href="/my-passes" className="mt-3 inline-block text-sm font-semibold underline underline-offset-4">Open my passes</Link>
    </motion.div>
  );

  if (state === "confirmed") return done(<CheckCircle2 className="h-5 w-5 text-emerald-600" />, "You are registered");
  if (state === "waiting") return done(<Clock className="h-5 w-5 text-brand" />, "Request sent", "The organisers will confirm your spot. It will show here once approved.");
  if (state === "rejected") return done(<XCircle className="h-5 w-5 text-red-600" />, "Not approved", "The organisers could not confirm this registration.");
  if (isFest && !needsRegistration && hasFestPass) return done(<Ticket className="h-5 w-5 text-chip-ink" />, "Entry included", "No registration needed. Your fest pass gets you in.");

  return (
    <div className="space-y-3">
      <ErrorNote>{error}</ErrorNote>
      <Button onClick={act} disabled={busy || state === "unknown"} size="lg" className="w-full">{busy ? "Please wait…" : needsRegistration ? "Register" : isFest ? "Get free fest pass" : "Register"}</Button>
      {isFest && !needsRegistration && <p className="text-center text-xs text-mute">No registration needed. The free fest pass covers entry.</p>}
      {needsRegistration && event.approval_mode === "manual" && <p className="text-center text-xs text-mute">The organisers approve each registration.</p>}
      {!event.is_free && event.price > 0 && <p className="text-center text-xs text-mute">Online payment is not available yet. The organisers will tell you how to pay.</p>}
    </div>
  );
}
