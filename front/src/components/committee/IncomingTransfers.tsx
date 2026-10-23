"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FestTransfer } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/bits";
import { useMyFests } from "./CommitteeShell";

/** Fests another organiser has offered to hand over to you. */
export function IncomingTransfers() {
  const router = useRouter();
  const { reload } = useMyFests();
  const [offers, setOffers] = useState<FestTransfer[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(() => { api<FestTransfer[]>("/api/users/me/fest-transfers").then(setOffers).catch(() => {}); }, []);
  useEffect(load, [load]);

  const answer = async (t: FestTransfer, accept: boolean) => {
    setBusy(true); setError("");
    try {
      await api(`/api/fest-transfers/${t.id}/${accept ? "accept" : "decline"}`, { method: "POST" });
      load(); reload();
      if (accept) router.push(`/dashboard/fests/${t.fest_slug}`);
    } catch (err) { setError(err instanceof Error ? err.message : "That did not work."); }
    setBusy(false);
  };

  if (offers.length === 0) return null;
  return (
    <section className="space-y-3">
      <ErrorNote>{error}</ErrorNote>
      {offers.map((t) => (
        <div key={t.id} className="card flex flex-wrap items-center justify-between gap-4 border-2 border-brand p-5">
          <p><strong>{t.from_name}</strong> wants to make you the director of <strong>{t.fest_name}</strong>.{t.keep_previous_owner ? " They will stay on as core team." : ""}</p>
          <div className="flex gap-2"><Button size="sm" disabled={busy} onClick={() => answer(t, true)}>Accept</Button><Button size="sm" variant="outline" disabled={busy} onClick={() => answer(t, false)}>Decline</Button></div>
        </div>
      ))}
    </section>
  );
}
