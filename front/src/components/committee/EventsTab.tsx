"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import type { Fest, ManagedEvent } from "@/lib/types";
import { formatDay, priceLabel } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote } from "@/components/ui/bits";
import { Field, Notice } from "@/components/ui/form";

const CATEGORIES = ["Cultural", "Technical", "Sports", "Music", "Business", "Gaming", "Fashion", "Literary", "Technology", "Finance", "Design", "Education"];

interface FormState {
  title: string; description: string; date: string; time: string; location: string; category: string; image_url: string;
  paid: boolean; price: string; requires_registration: boolean; registration_limit: string; approval_mode: "auto" | "manual";
}

const empty: FormState = { title: "", description: "", date: "", time: "", location: "", category: "", image_url: "", paid: false, price: "", requires_registration: false, registration_limit: "", approval_mode: "auto" };

const toForm = (e: ManagedEvent): FormState => ({
  title: e.title, description: e.description ?? "", date: e.date.slice(0, 10), time: e.time ?? "", location: e.location ?? "",
  category: e.category ?? "", image_url: e.image_url ?? "", paid: !e.is_free, price: e.is_free ? "" : String(e.price),
  requires_registration: e.requires_registration, registration_limit: e.registration_limit == null ? "" : String(e.registration_limit),
  approval_mode: e.approval_mode,
});

const toPayload = (f: FormState) => ({
  title: f.title.trim(),
  description: f.description || null,
  date: `${f.date}T00:00:00`,
  time: f.time || null,
  location: f.location || null,
  category: f.category || null,
  image_url: f.image_url || null,
  is_free: !f.paid,
  price: f.paid ? parseFloat(f.price) : 0,
  requires_registration: f.requires_registration,
  is_paid: f.requires_registration && f.paid,
  registration_limit: f.requires_registration && f.registration_limit ? parseInt(f.registration_limit, 10) : null,
  approval_mode: f.approval_mode,
});

function EventForm({ fest, event, onSaved, onCancel }: { fest: Fest; event: ManagedEvent | null; onSaved: () => void; onCancel: () => void }) {
  const [form, setForm] = useState<FormState>(event ? toForm(event) : empty);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm((f) => ({ ...f, [k]: v }));
  const locked = !!event && event.registration_count > 0;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const payload = toPayload(form);
      if (event) {
        // Send only what changed: registration settings are locked once people have registered, even if re-sent unchanged
        const before = toPayload(toForm(event)) as Record<string, unknown>;
        const changed = Object.fromEntries(Object.entries(payload).filter(([k, v]) => v !== before[k]));
        if (Object.keys(changed).length > 0) await api(`/api/events/${event.id}`, { method: "PATCH", body: changed });
      } else {
        await api("/api/events/", { method: "POST", body: { ...payload, event_type: "fest", fest_id: fest.id, college_id: fest.college_id } });
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the event.");
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="glass-strong space-y-4 rounded-[2rem] p-6 sm:p-8">
      <h2 className="font-display text-xl font-extrabold tracking-tight">{event ? "Edit event" : "New event"}</h2>
      <ErrorNote>{error}</ErrorNote>
      <Field label="Title"><input className="field" required value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="e.g. Battle of Bands" /></Field>
      <Field label="Description"><textarea className="field min-h-24 resize-y" value={form.description} onChange={(e) => set("description", e.target.value)} /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Date"><input className="field" type="date" required value={form.date} onChange={(e) => set("date", e.target.value)} /></Field>
        <Field label="Time"><input className="field" type="time" value={form.time} onChange={(e) => set("time", e.target.value)} /></Field>
      </div>
      <Field label="Venue"><input className="field" value={form.location} onChange={(e) => set("location", e.target.value)} placeholder="e.g. Main Auditorium" /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Category">
          <select className="field" value={form.category} onChange={(e) => set("category", e.target.value)}>
            <option value="">Select</option>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Cover image URL"><input className="field" type="url" value={form.image_url} onChange={(e) => set("image_url", e.target.value)} placeholder="https://…" /></Field>
      </div>

      <div className="space-y-4 rounded-2xl bg-black/[0.03] p-4">
        <label className="flex items-center gap-3 text-sm font-medium">
          <input type="checkbox" className="h-4 w-4 accent-[#f5a300]" checked={form.requires_registration} disabled={locked} onChange={(e) => set("requires_registration", e.target.checked)} />
          Students must register for this event
        </label>
        {locked && <p className="text-xs text-neutral-500">Registration settings are locked because people have already registered.</p>}
        {form.requires_registration && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Seat limit" hint="Leave empty for no limit"><input className="field" type="number" min={1} value={form.registration_limit} onChange={(e) => set("registration_limit", e.target.value)} /></Field>
            <Field label="Approval">
              <select className="field" value={form.approval_mode} onChange={(e) => set("approval_mode", e.target.value as "auto" | "manual")}>
                <option value="auto">Automatic: confirmed instantly</option>
                <option value="manual">Manual: committee approves each one</option>
              </select>
            </Field>
          </div>
        )}
        <label className="flex items-center gap-3 text-sm font-medium">
          <input type="checkbox" className="h-4 w-4 accent-[#f5a300]" checked={form.paid} disabled={locked} onChange={(e) => set("paid", e.target.checked)} />
          Paid event
        </label>
        {form.paid && (
          <>
            <Field label="Price (₹)"><input className="field" type="number" min={1} required value={form.price} onChange={(e) => set("price", e.target.value)} /></Field>
            <Notice tone="warn">Online payment is not live yet. Students who register for a paid event are marked as paid without being charged, so collect the money yourselves for now.</Notice>
          </>
        )}
      </div>

      <div className="flex gap-3">
        <Button type="submit" disabled={busy}>{busy ? "Saving…" : event ? "Save changes" : "Publish event"}</Button>
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
      {!event && <p className="text-xs text-neutral-500">Events show on your fest page as soon as you publish, once the fest itself is live.</p>}
    </form>
  );
}

export function EventsTab({ fest, events, reload }: { fest: Fest; events: ManagedEvent[]; reload: () => void }) {
  const [editing, setEditing] = useState<ManagedEvent | "new" | null>(null);
  if (editing) {
    return <EventForm fest={fest} event={editing === "new" ? null : editing} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); reload(); }} />;
  }
  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <p className="text-sm text-neutral-500">{events.length} event{events.length === 1 ? "" : "s"}</p>
        <Button size="sm" onClick={() => setEditing("new")}><Plus className="h-4 w-4" /> New event</Button>
      </div>
      {events.length === 0 ? (
        <EmptyState title="No events yet" body="Add your first event and it appears on your fest page." action={<Button onClick={() => setEditing("new")}>Add an event</Button>} />
      ) : (
        <div className="space-y-3">
          {events.map((e) => (
            <div key={e.id} className="glass flex flex-wrap items-center justify-between gap-4 rounded-3xl p-5">
              <div className="min-w-0">
                <p className="font-semibold">{e.title}</p>
                <p className="mt-0.5 text-sm text-neutral-500">{formatDay(e.date)}{e.time ? ` · ${e.time}` : ""}{e.location ? ` · ${e.location}` : ""} · {priceLabel(e)}</p>
                <p className="mt-1 text-sm text-neutral-600">
                  {e.requires_registration
                    ? `${e.registration_count}${e.registration_limit ? ` / ${e.registration_limit}` : ""} registered${e.pending_count ? ` · ${e.pending_count} waiting` : ""}`
                    : "No registration needed"}
                </p>
              </div>
              <div className="flex gap-2">
                <Button href={`/events/${e.id}`} variant="ghost" size="sm">View</Button>
                <Button variant="glass" size="sm" onClick={() => setEditing(e)}>Edit</Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

