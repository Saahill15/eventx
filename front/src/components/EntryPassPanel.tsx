"use client";

import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { FestPass } from "@/lib/types";
import { Button } from "./ui/Button";
import { ErrorNote } from "./ui/bits";

/** Pricing-style card for the free fest pass. */
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
    <div id="pass" className="rounded-3xl bg-brand p-8 text-on-brand shadow-[var(--shadow-glow)] sm:p-10">
      <p className="text-sm font-semibold text-on-brand/80">Fest pass</p>
      <p className="mt-1 font-display text-6xl font-semibold tracking-tight">Free</p>
      <p className="mt-2 text-on-brand/80">{name}</p>
      <ul className="mt-6 space-y-3">{["Entry to the fest with a QR code", "Register for any event", "Keep every pass in one place"].map((t) => <li key={t} className="flex items-center gap-2.5"><Check className="h-4 w-4" />{t}</li>)}</ul>
      <div className="mt-8 space-y-3">
        <ErrorNote>{error}</ErrorNote>
        {loading ? <div className="h-14 animate-pulse rounded-full bg-white/20" /> : pass ? (
          <Button href="/my-passes" variant="outline" size="lg" className="w-full !text-chip-ink">You have your pass. View it</Button>
        ) : user ? (
          <Button onClick={claim} disabled={busy} variant="outline" size="lg" className="w-full !text-chip-ink">{busy ? "Getting pass…" : "Get my free pass"}</Button>
        ) : (
          <Button href={`/login?next=${encodeURIComponent(`/fest/${slug}`)}`} variant="outline" size="lg" className="w-full !text-chip-ink">Sign in to get it</Button>
        )}
      </div>
    </div>
  );
}
