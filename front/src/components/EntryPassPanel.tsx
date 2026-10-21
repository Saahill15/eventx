"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { QrCode } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { FestPass } from "@/lib/types";
import { Button } from "./ui/Button";
import { ErrorNote } from "./ui/bits";

export function EntryPassPanel({ slug, isLive }: { slug: string; isLive: boolean }) {
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
    <div className="glass-strong flex flex-col gap-4 rounded-3xl p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
      <div className="flex items-start gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-hive-100 text-hive-ink"><QrCode className="h-6 w-6" /></div>
        <div>
          <p className="font-display text-lg font-extrabold tracking-tight">{pass ? "You have your fest pass" : "Get your free fest pass"}</p>
          <p className="text-sm text-neutral-500">{pass ? "Show the QR code at the gate and register for events below." : "You need it to enter and to register for events. It takes one tap."}</p>
          <div className="mt-2"><ErrorNote>{error}</ErrorNote></div>
        </div>
      </div>
      {loading ? null : pass ? (
        <Button href="/my-passes" variant="dark">View my pass</Button>
      ) : user ? (
        <Button onClick={claim} disabled={busy}>{busy ? "Getting pass…" : "Get my pass"}</Button>
      ) : (
        <Button href={`/login?next=${encodeURIComponent(`/fest/${slug}`)}`}>Sign in to get it</Button>
      )}
      {!user && !loading && <Link href={`/signup?next=${encodeURIComponent(`/fest/${slug}`)}`} className="sr-only">Create account</Link>}
    </div>
  );
}
