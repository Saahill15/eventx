"use client";

import { useEffect, useState } from "react";
import { QrCode } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { FestPass } from "@/lib/types";
import { Button } from "./ui/Button";
import { ErrorNote } from "./ui/bits";
import { TicketShell } from "./TicketShell";

export function EntryPassPanel({ slug, name, isLive }: { slug: string; name: string; isLive: boolean }) {
  const { user, loading } = useAuth();
  const [pass, setPass] = useState<FestPass | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) { setPass(null); return; }
    api<FestPass>(`/api/fests/${slug}/my-pass`).then(setPass).catch(() => setPass(null));
  }, [user, slug]);

  if (!isLive) return null;

  const claim = async () => {
    setBusy(true); setError("");
    try { setPass(await api<FestPass>(`/api/fests/${slug}/entry-pass`, { method: "POST" })); }
    catch (e) { setError(e instanceof Error ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  };

  return (
    <TicketShell
      head={<div className="flex items-start justify-between gap-3"><div><p className="text-[11px] font-bold uppercase tracking-[0.18em] text-amber-ink">Fest pass</p><p className="mt-1 font-display text-2xl font-bold leading-tight tracking-tight">{name}</p></div><QrCode className="h-8 w-8 text-amber-ink" /></div>}
    >
      <p className="mb-4 text-sm text-mute">{pass ? "You are in. Show the QR code at the gate and register for events." : "Free for everyone. You need it to enter and to register for events."}</p>
      <ErrorNote>{error}</ErrorNote>
      <div className={error ? "mt-3" : ""}>
        {loading ? <div className="h-14 animate-pulse rounded-full bg-wash" /> : pass ? <Button href="/my-passes" variant="ink" size="lg" className="w-full">View my pass</Button> : user ? <Button onClick={claim} disabled={busy} size="lg" className="w-full">{busy ? "Getting pass…" : "Get my free pass"}</Button> : <Button href={`/login?next=${encodeURIComponent(`/fest/${slug}`)}`} size="lg" className="w-full">Sign in to get it</Button>}
      </div>
    </TicketShell>
  );
}
