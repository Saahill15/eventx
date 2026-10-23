"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "./ui/Button";
import { ErrorNote, Field } from "./ui/bits";

const latestBirthday = () => new Date(new Date().setFullYear(new Date().getFullYear() - 13)).toISOString().slice(0, 10);

/**
 * Accounts that did not come through the sign-up form (Google, or older accounts) add the two things the form asks for:
 * a date of birth and accepting the terms. Shown before anything else, once.
 */
export function CompleteProfile() {
  const { user, refresh, logout } = useAuth();
  const [dob, setDob] = useState("");
  const [terms, setTerms] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!user || user.role === "admin" || user.profile_complete) return null;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try { await api("/api/users/me/complete-profile", { method: "POST", body: { date_of_birth: user.date_of_birth ?? dob, accept_terms: terms } }); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not save."); setBusy(false); }
  };

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="finish-title" className="fixed inset-0 z-[115] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
      <form onSubmit={save} className="card w-full max-w-md space-y-5 p-8 shadow-[var(--shadow-pop)]">
        <div>
          <h2 id="finish-title" className="font-display text-3xl font-bold tracking-tight">One last step{user.first_name ? `, ${user.first_name}` : ""}</h2>
          <p className="mt-2 text-mute">We need these once before you can use HiveOut.</p>
        </div>
        <ErrorNote>{error}</ErrorNote>
        {!user.date_of_birth && <Field label="Date of birth" hint="You need to be at least 13."><input className="field" type="date" required autoComplete="bday" min="1920-01-01" max={latestBirthday()} value={dob} onChange={(e) => setDob(e.target.value)} /></Field>}
        <label className="flex items-start gap-3 text-sm text-neutral-700">
          <input type="checkbox" required className="mt-0.5 h-4 w-4 accent-[#111]" checked={terms} onChange={(e) => setTerms(e.target.checked)} />
          <span>I agree to HiveOut&apos;s terms of use and privacy policy.</span>
        </label>
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-between">
          <Button type="button" variant="ghost" onClick={logout}>Sign out</Button>
          <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Continue"}</Button>
        </div>
      </form>
    </div>
  );
}
