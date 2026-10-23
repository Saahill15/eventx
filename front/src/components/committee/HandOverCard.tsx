"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FestTransfer } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Field, Notice } from "@/components/ui/bits";

/** The fest's director offers the fest to another organiser. Nothing changes until that person accepts. */
export function HandOverCard({ slug, collegeName }: { slug: string; collegeName?: string | null }) {
  const [offer, setOffer] = useState<FestTransfer | null | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [keepMe, setKeepMe] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => { api<FestTransfer | null>(`/api/fests/${slug}/transfer`).then(setOffer).catch(() => setOffer(null)); }, [slug]);
  useEffect(load, [load]);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try { setOffer(await api<FestTransfer>(`/api/fests/${slug}/transfer`, { method: "POST", body: { email: email.trim(), keep_me: keepMe } })); setOpen(false); setEmail(""); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not send the offer."); }
    setBusy(false);
  };
  const withdraw = async () => {
    setBusy(true); setError("");
    try { await api(`/api/fests/${slug}/transfer`, { method: "DELETE" }); load(); } catch (err) { setError(err instanceof Error ? err.message : "Could not withdraw."); }
    setBusy(false);
  };

  if (offer === undefined) return null;
  return (
    <section className="card space-y-4 p-6 sm:p-8">
      <div>
        <h2 className="font-display text-xl font-bold tracking-tight">Hand over this fest</h2>
        <p className="mt-1 text-sm text-mute">Make another organiser{collegeName ? ` from ${collegeName}` : ""} the festival director. They have to accept first, and only then does anything change.</p>
      </div>
      <ErrorNote>{error}</ErrorNote>
      {offer ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-wash p-4">
          <p className="text-sm">Waiting for <strong>{offer.to_name}</strong> ({offer.to_email}) to accept. {offer.keep_previous_owner ? "You will stay on as core team." : "You will leave the team."}</p>
          <Button size="sm" variant="outline" disabled={busy} onClick={withdraw}>Withdraw offer</Button>
        </div>
      ) : open ? (
        <form onSubmit={send} className="space-y-4">
          <Field label="Their HiveOut email" hint="They must already be an organiser for this fest's college."><input className="field" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          <label className="flex items-center gap-3 text-sm font-medium"><input type="checkbox" className="h-4 w-4 accent-[#111]" checked={keepMe} onChange={(e) => setKeepMe(e.target.checked)} /> Keep me on the team as core team</label>
          <Notice tone="warn">Once they accept, they run the fest and you cannot take it back yourself.</Notice>
          <div className="flex gap-2"><Button type="submit" disabled={busy}>{busy ? "Sending…" : "Send offer"}</Button><Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button></div>
        </form>
      ) : <Button variant="outline" onClick={() => setOpen(true)}>Hand over…</Button>}
    </section>
  );
}
