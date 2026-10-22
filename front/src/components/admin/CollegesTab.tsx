"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AdminCollege } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Pill, Skeleton } from "@/components/ui/bits";
import { Chips, useAction } from "./shared";

const blank = (v: string) => (v.trim() ? v.trim() : null);

function Editor({ c, onSaved, onCancel }: { c: AdminCollege | null; onSaved: () => void; onCancel: () => void }) {
  const [f, setF] = useState({
    name: c?.name ?? "", area: c?.area ?? "", website: c?.website ?? "", email_domains: c?.email_domains ?? "",
    partner_status: c?.partner_status ?? "prospect", coordinator_name: c?.coordinator_name ?? "", coordinator_phone: c?.coordinator_phone ?? "",
    coordinator_email: c?.coordinator_email ?? "", partner_since: c?.partner_since ?? "", partner_notes: c?.partner_notes ?? "",
  });
  const act = useAction(() => {});
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF((x) => ({ ...x, [k]: e.target.value }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const body = {
      name: f.name.trim(), area: blank(f.area), website: blank(f.website), email_domains: blank(f.email_domains), emoji: c?.emoji ?? "🏛️",
      partner_status: f.partner_status, coordinator_name: blank(f.coordinator_name), coordinator_phone: blank(f.coordinator_phone),
      coordinator_email: blank(f.coordinator_email), partner_since: blank(f.partner_since), partner_notes: blank(f.partner_notes),
    };
    if (await act.run(() => api(c ? `/api/colleges/${c.id}` : "/api/colleges/", { method: c ? "PUT" : "POST", body }))) onSaved();
  };

  return (
    <form onSubmit={save} className="card mb-4 space-y-4 p-6">
      <h3 className="font-display text-lg font-semibold">{c ? `Edit ${c.name}` : "Add a college"}</h3>
      <ErrorNote>{act.error}</ErrorNote>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="College name"><input className="field" required value={f.name} onChange={set("name")} /></Field>
        <Field label="Area"><input className="field" value={f.area} onChange={set("area")} placeholder="Powai, Mumbai" /></Field>
        <Field label="Website"><input className="field" value={f.website} onChange={set("website")} placeholder="https://…" /></Field>
        <Field label="Student email domains" hint="Comma-separated, e.g. iitb.ac.in. Lets students verify by email."><input className="field" value={f.email_domains} onChange={set("email_domains")} /></Field>
        <Field label="Status" hint="Only partner colleges can have fests listed."><select className="field" value={f.partner_status} onChange={set("partner_status")}><option value="prospect">Prospect</option><option value="partner">Partner</option></select></Field>
        <Field label="Partner since"><input className="field" type="date" value={f.partner_since} onChange={set("partner_since")} /></Field>
        <Field label="Coordinator name"><input className="field" value={f.coordinator_name} onChange={set("coordinator_name")} /></Field>
        <Field label="Coordinator phone"><input className="field" value={f.coordinator_phone} onChange={set("coordinator_phone")} placeholder="+91 98765 43210" /></Field>
        <Field label="Coordinator email"><input className="field" type="email" value={f.coordinator_email} onChange={set("coordinator_email")} /></Field>
      </div>
      <Field label="Private notes" hint="Only admins see partnership details."><textarea className="field min-h-20" value={f.partner_notes} onChange={set("partner_notes")} maxLength={2000} /></Field>
      <div className="flex gap-2"><Button type="submit" disabled={act.busy}>{act.busy ? "Saving…" : "Save"}</Button><Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button></div>
    </form>
  );
}

export function CollegesTab() {
  const [rows, setRows] = useState<AdminCollege[] | null>(null);
  const [filter, setFilter] = useState<"all" | "partner" | "prospect">("all");
  const [editing, setEditing] = useState<AdminCollege | "new" | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => { api<AdminCollege[]>("/api/admin/colleges").then((r) => { setRows(r); setError(""); }).catch((e) => { setError(e instanceof Error ? e.message : "Could not load."); setRows([]); }); }, []);
  useEffect(load, [load]);
  const act = useAction(load);
  const shown = (rows ?? []).filter((c) => filter === "all" || (c.partner_status ?? "prospect") === filter);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Chips value={filter} onChange={setFilter} options={[{ id: "all", label: "All" }, { id: "partner", label: "Partners" }, { id: "prospect", label: "Prospects" }]} />
        {editing === null && <Button onClick={() => setEditing("new")}>Add college</Button>}
      </div>
      <ErrorNote>{error || act.error}</ErrorNote>
      {editing && <Editor key={editing === "new" ? "new" : editing.id} c={editing === "new" ? null : editing} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
      {rows === null ? <Skeleton className="h-40" /> : shown.length === 0 ? <EmptyState title="No colleges" body="Add the first one." /> : (
        <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(20rem,1fr))]">
          {shown.map((c) => (
            <div key={c.id} className="card p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-semibold">{c.name}</p>
                  <p className="truncate text-xs text-mute">{[c.area, `${c.event_count} event${c.event_count === 1 ? "" : "s"}`].filter(Boolean).join(" · ")}</p>
                </div>
                <Pill tone={c.partner_status === "partner" ? "green" : "neutral"}>{c.partner_status === "partner" ? "Partner" : "Prospect"}</Pill>
              </div>
              {(c.coordinator_name || c.coordinator_phone) && <p className="mt-3 text-sm text-neutral-700">{[c.coordinator_name, c.coordinator_phone, c.coordinator_email].filter(Boolean).join(" · ")}</p>}
              <div className="mt-4 flex gap-3 text-sm font-semibold">
                <button onClick={() => { setEditing(c); window.scrollTo({ top: 0, behavior: "smooth" }); }} className="hover:underline">Edit</button>
                <button disabled={act.busy} onClick={() => window.confirm(`Delete ${c.name}? Its events stay but are unlinked from the college.`) && act.run(() => api(`/api/colleges/${c.id}`, { method: "DELETE" }))} className="text-red-600 hover:underline">Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
