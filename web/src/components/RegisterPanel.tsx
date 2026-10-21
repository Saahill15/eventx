"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Clock, Ticket } from "lucide-react";
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
    } catch {
      setState("none");
    }
  }, [event.id, event.fest_slug, isFest, needsRegistration]);

  useEffect(() => { if (user) refresh(); }, [user, refresh]);

  const act = async () => {
    setBusy(true); setError("");
    try {
      if (needsRegistration) {
        await api(`/api/fests/${event.fest_slug}/entry-pass`, { method: "POST" });
        await api(`/api/fest-events/${event.id}/register`, { method: "POST" });
      } else if (isFest) {
        await api(`/api/fests/${event.fest_slug}/entry-pass`, { method: "POST" });
      } else {
        await api(`/api/passes/${event.id}/register`, { method: "POST" });
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  if (hasEnded) return <p className="rounded-2xl bg-black/5 px-4 py-3 text-center text-sm font-medium text-neutral-600">This event has already taken place.</p>;
  if (loading) return <div className="h-12 animate-pulse rounded-full bg-black/5" />;

  if (!user) {
    return (
      <div className="space-y-3">
        <Button href={`/login?next=${next}`} size="lg" className="w-full">Sign in to {needsRegistration || !isFest ? "register" : "get your pass"}</Button>
        <p className="text-center text-xs text-neutral-500">New here? <Link href={`/signup?next=${next}`} className="font-semibold text-hive-ink">Create a free account</Link></p>
      </div>
    );
  }

  if (state === "confirmed") {
    return <Done icon={<CheckCircle2 className="h-5 w-5 text-emerald-600" />} title="You are registered" />;
  }
  if (state === "waiting") {
    return <Done icon={<Clock className="h-5 w-5 text-amber-600" />} title="Request sent" body="The organisers will confirm your spot. We will show it here once approved." />;
  }
  if (state === "rejected") {
    return <Done icon={<Clock className="h-5 w-5 text-red-600" />} title="Not approved" body="The organisers could not confirm this registration." />;
  }
  if (isFest && !needsRegistration && hasFestPass) {
    return <Done icon={<Ticket className="h-5 w-5 text-hive-ink" />} title="Entry included" body="No registration needed. Your fest pass gets you in." />;
  }

  return (
    <div className="space-y-3">
      <ErrorNote>{error}</ErrorNote>
      <Button onClick={act} disabled={busy || state === "unknown"} size="lg" className="w-full">
        {busy ? "Please wait…" : needsRegistration ? "Register" : isFest ? "Get free fest pass" : "Register"}
      </Button>
      {isFest && !needsRegistration && <p className="text-center text-xs text-neutral-500">No registration needed. The free fest pass covers entry.</p>}
      {needsRegistration && event.approval_mode === "manual" && <p className="text-center text-xs text-neutral-500">The organisers approve each registration.</p>}
      {!event.is_free && event.price > 0 && <p className="text-center text-xs text-neutral-500">Online payment is not available yet. The organisers will tell you how to pay.</p>}
    </div>
  );
}

function Done({ icon, title, body }: { icon: React.ReactNode; title: string; body?: string }) {
  return (
    <div className="rounded-2xl bg-white/70 p-4">
      <p className="flex items-center gap-2 font-semibold">{icon} {title}</p>
      {body && <p className="mt-1 text-sm text-neutral-500">{body}</p>}
      <Link href="/my-passes" className="mt-3 inline-block text-sm font-semibold text-hive-ink">Open My passes →</Link>
    </div>
  );
}
