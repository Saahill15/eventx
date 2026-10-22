"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ExtraSection, FestEvent, FestManage, ManagedEvent, Question } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Field, Notice } from "@/components/ui/bits";
import { ImageUpload } from "@/components/ui/ImageUpload";
import { SectionsEditor } from "./SectionsEditor";
import { QuestionsEditor, toDraft, toQuestionPayload, type QuestionDraft } from "./QuestionsEditor";

export const CATEGORIES = ["Cultural", "Technical", "Sports", "Music", "Business", "Gaming", "Fashion", "Literary", "Technology", "Finance", "Design", "Education"];

interface State {
  title: string; description: string; date: string; time: string; end_time: string; location: string; category: string;
  paid: boolean; price: string; students_only: boolean; student_price: string;
  requires_registration: boolean; registration_limit: string; approval_mode: "auto" | "manual";
}
const empty: State = { title: "", description: "", date: "", time: "", end_time: "", location: "", category: "", paid: false, price: "", students_only: false, student_price: "", requires_registration: false, registration_limit: "", approval_mode: "auto" };
const toState = (e: FestEvent): State => ({
  title: e.title, description: e.description ?? "", date: e.date.slice(0, 10), time: e.time ?? "", end_time: e.end_time ?? "", location: e.location ?? "", category: e.category ?? "",
  paid: !e.is_free, price: e.is_free ? "" : String(e.price), students_only: e.students_only, student_price: e.student_price == null ? "" : String(e.student_price),
  requires_registration: e.requires_registration, registration_limit: e.registration_limit == null ? "" : String(e.registration_limit), approval_mode: e.approval_mode,
});

const payloadOf = (f: State, image: string | null, sections: ExtraSection[], fest: boolean) => ({
  title: f.title.trim(), description: f.description.trim() || null, date: `${f.date}T00:00:00`, time: f.time || null, end_time: f.end_time || null,
  location: f.location.trim() || null, category: f.category || null, image_url: image,
  is_free: !f.paid, price: f.paid ? parseFloat(f.price) || 0 : 0, students_only: f.students_only, student_price: f.paid && f.student_price ? parseFloat(f.student_price) : null,
  requires_registration: fest && f.requires_registration, is_paid: fest && f.requires_registration && f.paid,
  registration_limit: fest && f.requires_registration && f.registration_limit ? parseInt(f.registration_limit, 10) : null, approval_mode: f.approval_mode,
  extra_sections: sections.filter((s) => s.title.trim() && s.body.trim()),
});

/** One form for both kinds of event: a fest's events (with registration and questions) and standalone city events. */
export function EventForm({ kind, fest, event, onSaved, onCancel }: { kind: "fest" | "city"; fest?: FestManage; event: ManagedEvent | FestEvent | null; onSaved: () => void; onCancel: () => void }) {
  const isFest = kind === "fest";
  const [f, setF] = useState<State>(event ? toState(event) : empty);
  const [image, setImage] = useState<string | null>(event?.image_url ?? null);
  const [sections, setSections] = useState<ExtraSection[]>(event?.extra_sections ?? []);
  const [questions, setQuestions] = useState<QuestionDraft[]>([]);
  const [loadedQuestions, setLoadedQuestions] = useState("[]");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = <K extends keyof State>(k: K, v: State[K]) => setF((x) => ({ ...x, [k]: v }));
  const registered = event && "registration_count" in event ? event.registration_count : 0;
  const locked = registered > 0;

  useEffect(() => {
    if (!event || !isFest) return;
    api<Question[]>(`/api/events/${event.id}/questions`).then((qs) => { const d = qs.map(toDraft); setQuestions(d); setLoadedQuestions(JSON.stringify(toQuestionPayload(d))); }).catch(() => {});
  }, [event, isFest]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const payload = payloadOf(f, image, sections, isFest);
      let id = event?.id;
      if (event) {
        // Send only what changed: some settings are locked once people have registered, even if re-sent unchanged
        const before = payloadOf(toState(event), event.image_url, event.extra_sections ?? [], isFest) as Record<string, unknown>;
        const changed = Object.fromEntries(Object.entries(payload).filter(([k, v]) => JSON.stringify(v) !== JSON.stringify(before[k])));
        if (Object.keys(changed).length > 0) await api(`/api/events/${event.id}`, { method: "PATCH", body: changed });
      } else {
        const created = await api<FestEvent>("/api/events/", { method: "POST", body: { ...payload, event_type: kind, fest_id: isFest ? fest!.id : null, college_id: isFest ? fest!.college_id : null } });
        id = created.id;
      }
      if (isFest && id && f.requires_registration) {
        const qs = toQuestionPayload(questions);
        if (JSON.stringify(qs) !== loadedQuestions) await api(`/api/events/${id}/questions`, { method: "PUT", body: { questions: qs } });
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the event.");
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="card max-w-4xl space-y-5 p-6 sm:p-8">
      <h2 className="font-display text-xl font-bold tracking-tight">{event ? "Edit event" : isFest ? "New event" : "New city event"}</h2>
      <ErrorNote>{error}</ErrorNote>
      {!isFest && <Notice tone="info">City events are standalone events, not part of a fest. HiveOut reviews each one before it appears on the site.</Notice>}
      <Field label="Title"><input className="field" required value={f.title} onChange={(e) => set("title", e.target.value)} placeholder="e.g. Battle of Bands" /></Field>
      <Field label="Description" hint={isFest ? "Required" : undefined}><textarea className="field min-h-28" required={isFest} value={f.description} onChange={(e) => set("description", e.target.value)} /></Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Date"><input className="field" type="date" required value={f.date} min={isFest ? fest?.start_date ?? undefined : undefined} max={isFest ? fest?.end_date ?? undefined : undefined} onChange={(e) => set("date", e.target.value)} /></Field>
        <Field label="Starts"><input className="field" type="time" required={isFest} value={f.time} onChange={(e) => set("time", e.target.value)} /></Field>
        <Field label="Ends"><input className="field" type="time" required={isFest} value={f.end_time} onChange={(e) => set("end_time", e.target.value)} /></Field>
      </div>
      {isFest && fest?.start_date && fest?.end_date && <p className="-mt-3 text-xs text-mute">Events must fall between your fest&apos;s dates ({fest.start_date} to {fest.end_date}).</p>}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Venue"><input className="field" required={isFest} value={f.location} onChange={(e) => set("location", e.target.value)} placeholder="e.g. Main Auditorium" /></Field>
        <Field label="Category"><select className="field" value={f.category} onChange={(e) => set("category", e.target.value)}><option value="">Select</option>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select></Field>
      </div>
      <ImageUpload label="Cover image" value={image} onChange={setImage} aspect="aspect-[16/10]" />

      <div className="space-y-4 rounded-2xl bg-wash p-5">
        {isFest && (
          <>
            <label className="flex items-center gap-3 text-sm font-medium"><input type="checkbox" className="h-4 w-4 accent-[#111]" checked={f.requires_registration} disabled={locked} onChange={(e) => set("requires_registration", e.target.checked)} /> Students must register for this event</label>
            {locked && <p className="text-xs text-mute">Registration settings are locked because people have already registered.</p>}
            {f.requires_registration && (
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Seat limit" hint="Leave empty for no limit"><input className="field" type="number" min={1} value={f.registration_limit} onChange={(e) => set("registration_limit", e.target.value)} /></Field>
                <Field label="Approval"><select className="field" value={f.approval_mode} onChange={(e) => set("approval_mode", e.target.value as "auto" | "manual")}><option value="auto">Automatic: confirmed instantly</option><option value="manual">Manual: committee approves each one</option></select></Field>
              </div>
            )}
          </>
        )}
        <label className="flex items-center gap-3 text-sm font-medium"><input type="checkbox" className="h-4 w-4 accent-[#111]" checked={f.paid} disabled={locked} onChange={(e) => set("paid", e.target.checked)} /> Paid event</label>
        {f.paid && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Price (₹)"><input className="field" type="number" min={1} required value={f.price} onChange={(e) => set("price", e.target.value)} /></Field>
            <Field label="Student price (₹)" hint="Optional. Lower than the price, for verified students."><input className="field" type="number" min={0} disabled={locked} value={f.student_price} onChange={(e) => set("student_price", e.target.value)} /></Field>
          </div>
        )}
        {f.paid && <Notice tone="warn">Online payment is not live yet. Students who register for a paid event are marked as paid without being charged, so collect the money yourselves for now.</Notice>}
        <label className="flex items-center gap-3 text-sm font-medium"><input type="checkbox" className="h-4 w-4 accent-[#111]" checked={f.students_only} onChange={(e) => set("students_only", e.target.checked)} /> Only verified students can register</label>
      </div>

      {isFest && f.requires_registration && <QuestionsEditor value={questions} onChange={setQuestions} locked={locked} />}
      <SectionsEditor value={sections} onChange={setSections} hint="Rules, prizes, eligibility: shown on the event page." />

      <div className="flex gap-3">
        <Button type="submit" size="lg" disabled={busy}>{busy ? "Saving…" : event ? "Save changes" : isFest ? "Add event" : "Submit for approval"}</Button>
        <Button type="button" size="lg" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}
