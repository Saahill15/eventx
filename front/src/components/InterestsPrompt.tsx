"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Interest } from "@/lib/types";
import { Button } from "./ui/Button";

/**
 * Asked once, the first time someone signs in: what they like, so the home page can show it first.
 * Skipping counts as an answer (an empty list), so it is never asked again.
 */
export function InterestsPrompt() {
  const { user, refresh } = useAuth();
  const [all, setAll] = useState<Interest[]>([]);
  const [picked, setPicked] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // A newly promoted organiser sees their welcome first
  const show = !!user && user.role !== "admin" && !user.interests_set && !user.organizer_welcome_pending;

  useEffect(() => { if (show) api<Interest[]>("/api/users/interests/all").then(setAll).catch(() => {}); }, [show]);
  if (!show) return null;

  const save = async (ids: number[]) => {
    setBusy(true); setError("");
    try { await api("/api/users/interests", { method: "POST", body: { interest_ids: ids } }); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not save. Please try again."); setBusy(false); }
  };
  const toggle = (id: number) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="interests-title" className="fixed inset-0 z-[105] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
      <div className="card w-full max-w-lg p-8 shadow-[var(--shadow-pop)] sm:p-10">
        <h2 id="interests-title" className="font-display text-3xl font-bold tracking-tight">What are you into{user?.first_name ? `, ${user.first_name}` : ""}?</h2>
        <p className="mt-2 text-mute">Pick a few and we will show those events first. You can change this later.</p>
        <div className="mt-6 flex flex-wrap gap-2">
          {all.map((i) => (
            <button key={i.id} type="button" aria-pressed={picked.includes(i.id)} onClick={() => toggle(i.id)} className={`rounded-full px-4 py-2 text-sm font-semibold transition ${picked.includes(i.id) ? "bg-ink text-white" : "bg-wash text-neutral-700 hover:bg-chip"}`}>{i.name}</button>
          ))}
        </div>
        {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
        <div className="mt-8 flex flex-col gap-2 sm:flex-row sm:justify-end">
          <Button variant="ghost" disabled={busy} onClick={() => save([])}>Skip for now</Button>
          <Button disabled={busy || picked.length === 0} onClick={() => save(picked)}>{busy ? "Saving…" : "Save my picks"}</Button>
        </div>
      </div>
    </div>
  );
}
