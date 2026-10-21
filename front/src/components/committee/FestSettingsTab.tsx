"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Fest } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/bits";
import { Field } from "@/components/ui/bits";

export function FestSettingsTab({ fest, onSaved }: { fest: Fest; onSaved: () => void }) {
  const [form, setForm] = useState({ name: fest.name, tagline: fest.tagline ?? "", banner_url: fest.banner_url ?? "", logo_url: fest.logo_url ?? "" });
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const set = (k: keyof typeof form, v: string) => { setSaved(false); setForm((f) => ({ ...f, [k]: v })); };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api(`/api/fests/${fest.slug}`, { method: "PATCH", body: { name: form.name, tagline: form.tagline || null, banner_url: form.banner_url || null, logo_url: form.logo_url || null } });
      setSaved(true); onSaved();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save."); }
    finally { setBusy(false); }
  };

  return (
    <form onSubmit={submit} className="bg-white ring-1 ring-black/5 shadow-[var(--shadow-soft)] max-w-xl space-y-4 rounded-[2rem] p-6 sm:p-8">
      <ErrorNote>{error}</ErrorNote>
      <Field label="Fest name"><input className="field" required value={form.name} onChange={(e) => set("name", e.target.value)} /></Field>
      <Field label="Tagline"><input className="field" value={form.tagline} onChange={(e) => set("tagline", e.target.value)} /></Field>
      <Field label="Banner image URL" hint="Wide image shown at the top of your fest page"><input className="field" type="url" value={form.banner_url} onChange={(e) => set("banner_url", e.target.value)} placeholder="https://…" /></Field>
      <Field label="Logo URL"><input className="field" type="url" value={form.logo_url} onChange={(e) => set("logo_url", e.target.value)} placeholder="https://…" /></Field>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</Button>
        {saved && <span className="text-sm font-medium text-emerald-700">Saved</span>}
      </div>
    </form>
  );
}
