"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ExtraSection, FestEvent, FestManage, ManagedEvent, Question } from "@/lib/types";
import { formatDay, formatTime } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Field, Notice } from "@/components/ui/bits";
import { ImageUpload } from "@/components/ui/ImageUpload";
import { SectionsEditor } from "./SectionsEditor";
import { QuestionsEditor, toDraft, toQuestionPayload, type QuestionDraft } from "./QuestionsEditor";

export const CATEGORIES = ["Cultural", "Technical", "Sports", "Music", "Business", "Gaming", "Fashion", "Literary", "Technology", "Finance", "Design", "Education"];

/** When registration starts: at once, on a day, not decided yet. "closed" means the committee shut it by hand. */
type RegMode = "open_now" | "scheduled" | "not_set" | "closed";

interface State {
  title: string; description: string; date: string; span: string; time: string; end_time: string; location: string; category: string;
  paid: boolean; price: string; students_only: boolean; student_price: string;
  requires_registration: boolean; registration_limit: string; approval_mode: "auto" | "manual"; deadline: string;
  reg_mode: RegMode; opens_on: string;
  is_team_event: boolean; team_min: string; team_max: string;
  coordinator_name: string; coordinator_phone: string;
  scored: boolean; points: string[];   // a competition between colleges, and what each place earns
  entries: boolean; entries_per: string; entry_fee: string; entry_fee_per: "entry" | "participant"; entry_deadline: string;   // visiting colleges entering the event
}
const empty: State = {
  title: "", description: "", date: "", span: "1", time: "", end_time: "", location: "", category: "", paid: false, price: "", students_only: false, student_price: "",
  requires_registration: false, registration_limit: "", approval_mode: "auto", deadline: "", reg_mode: "not_set", opens_on: "", is_team_event: false, team_min: "2", team_max: "4", coordinator_name: "", coordinator_phone: "", scored: false, points: [], entries: false, entries_per: "1", entry_fee: "", entry_fee_per: "entry", entry_deadline: "",
};
const toState = (e: FestEvent): State => ({
  title: e.title, description: e.description ?? "", date: e.date.slice(0, 10), span: String(e.span_days ?? 1), time: e.time ?? "", end_time: e.end_time ?? "", location: e.location ?? "", category: e.category ?? "",
  paid: !e.is_free, price: e.is_free ? "" : String(e.price), students_only: e.students_only, student_price: e.student_price == null ? "" : String(e.student_price),
  requires_registration: e.requires_registration, registration_limit: e.registration_limit == null ? "" : String(e.registration_limit), approval_mode: e.approval_mode,
  deadline: e.registration_deadline ?? "", reg_mode: e.registration_mode ?? "open_now", opens_on: e.registration_opens_on ?? "", is_team_event: e.is_team_event, team_min: String(e.team_min ?? 2), team_max: String(e.team_max ?? 4),
  coordinator_name: e.coordinator_name ?? "", coordinator_phone: e.coordinator_phone ?? "",
  entries: !!e.contingent_entries, entries_per: String(e.entries_per_contingent ?? 1), entry_fee: e.entry_fee ? String(e.entry_fee) : "", entry_fee_per: e.entry_fee_per ?? "entry", entry_deadline: e.entry_deadline ?? "",
  scored: !!e.points_scheme, points: e.points_scheme ? Object.keys(e.points_scheme).map(Number).sort((a, b) => a - b).map((p) => String(e.points_scheme?.[String(p)] ?? 0)) : [],
});

const payloadOf = (f: State, image: string | null, sections: ExtraSection[], fest: boolean) => ({
  title: f.title.trim(), description: f.description.trim() || null, date: `${f.date}T00:00:00`, time: f.time || null, end_time: f.end_time || null,
  location: f.location.trim() || null, category: f.category || null, image_url: image,
  is_free: !f.paid, price: f.paid ? parseFloat(f.price) || 0 : 0, students_only: f.students_only, student_price: f.paid && f.student_price ? parseFloat(f.student_price) : null,
  requires_registration: fest && f.requires_registration, is_paid: fest && f.requires_registration && f.paid,
  registration_limit: fest && f.requires_registration && f.registration_limit ? parseInt(f.registration_limit, 10) : null, approval_mode: f.approval_mode,
  registration_deadline: fest && f.requires_registration && f.deadline ? f.deadline : null,
  ...(fest && f.requires_registration ? { registration_mode: f.reg_mode, registration_opens_on: f.reg_mode === "scheduled" && f.opens_on ? f.opens_on : null } : {}),
  extra_sections: sections.filter((s) => s.title.trim() && s.body.trim()),
  is_team_event: fest && f.requires_registration && f.is_team_event,
  team_min: fest && f.requires_registration && f.is_team_event ? parseInt(f.team_min, 10) || null : null,
  team_max: fest && f.requires_registration && f.is_team_event ? parseInt(f.team_max, 10) || null : null,
  ...(fest ? { contingent_entries: f.entries, entries_per_contingent: f.entries ? Math.max(1, parseInt(f.entries_per, 10) || 1) : 1, entry_fee: f.entries ? parseFloat(f.entry_fee) || 0 : 0, entry_fee_per: f.entry_fee_per, entry_deadline: f.entries && f.entry_deadline ? f.entry_deadline : null } : {}),
  ...(fest ? { points_scheme: f.scored && f.points.length > 0 ? Object.fromEntries(f.points.map((v, i) => [String(i + 1), Math.max(0, parseInt(v, 10) || 0)])) : null } : {}),
  ...(fest ? { span_days: parseInt(f.span, 10) || 1, coordinator_name: f.coordinator_name.trim() || null, coordinator_phone: f.coordinator_phone.trim() || null } : {}),
});

/** Starting points for a new fest event. They set how people join, team size, seats, usual times and the headings for rules and prizes. */
const TEMPLATES: { key: string; label: string; about: string; hint: string; minutes: number; sections: string[]; set: Partial<State> }[] = [
  { key: "competition", label: "Competition", about: "Solo entries, judged, with prizes", minutes: 180, hint: "Who can enter, what the task is and what makes a winner.", sections: ["Rules", "Prizes", "Judging"],
    set: { requires_registration: true, is_team_event: false, approval_mode: "auto", time: "11:00" } },
  { key: "team", label: "Team competition", about: "People enter as a team of 2 to 4", minutes: 180, hint: "What teams have to do, the rules and how it is judged.", sections: ["Rules", "Prizes", "Judging"],
    set: { requires_registration: true, is_team_event: true, team_min: "2", team_max: "4", time: "11:00" } },
  { key: "workshop", label: "Workshop", about: "Limited seats, hands on", minutes: 120, hint: "What people will learn, who it is for and what to bring.", sections: ["What you will learn", "What to bring"],
    set: { requires_registration: true, registration_limit: "60", category: "Education", time: "10:00" } },
  { key: "talk", label: "Talk or panel", about: "Open to walk in", minutes: 60, hint: "Who is speaking and what they will talk about.", sections: ["About the speakers"],
    set: { requires_registration: false, category: "Education", time: "15:00" } },
  { key: "show", label: "Concert or show", about: "Open to walk in", minutes: 180, hint: "Who is performing and what to expect.", sections: ["Line-up"],
    set: { requires_registration: false, category: "Music", time: "18:00" } },
  { key: "exhibition", label: "Exhibition or stalls", about: "Open to walk in, runs all day", minutes: 420, hint: "What is on display and what visitors can do.", sections: ["What is on display"],
    set: { requires_registration: false, time: "10:00" } },
];
/** What a template resets before it applies, so switching templates leaves nothing behind. */
const STRUCTURE_RESET: Partial<State> = { requires_registration: false, is_team_event: false, team_min: "2", team_max: "4", registration_limit: "", approval_mode: "auto", category: "", deadline: "" };

/** "11:00" plus 180 minutes is "14:00". Stops at the end of the day. */
function addMinutes(time: string, minutes: number): string {
  const [h, m] = time.split(":").map(Number);
  if (Number.isNaN(h)) return "";
  const total = Math.min(h * 60 + (m || 0) + minutes, 23 * 60 + 59);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}
/** "2026-12-04" plus 2 is "2026-12-06". */
function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const out = new Date(Date.UTC(y, m - 1, d + n));
  return out.toISOString().slice(0, 10);
}

function Section({ n, title, hint, children }: { n: number; title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4 border-t border-black/5 pt-6 first:border-0 first:pt-0" aria-label={title}>
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink text-xs font-bold text-white">{n}</span>
        <div><h3 className="font-display text-lg font-semibold tracking-tight">{title}</h3>{hint && <p className="text-sm text-mute">{hint}</p>}</div>
      </div>
      <div className="space-y-4 sm:pl-10">{children}</div>
    </section>
  );
}

function Choice({ checked, disabled, onChange, title, body, name }: { checked: boolean; disabled?: boolean; onChange: () => void; title: string; body?: string; name: string }) {
  return (
    <label className={`flex cursor-pointer items-start gap-3 rounded-2xl p-3.5 ring-1 transition ${checked ? "bg-white ring-ink" : "bg-white/60 ring-black/10 hover:ring-black/30"} ${disabled ? "cursor-not-allowed opacity-60" : ""}`}>
      <input type="radio" name={name} className="mt-1 h-4 w-4 accent-[#111]" checked={checked} disabled={disabled} onChange={onChange} />
      <span><span className="block text-sm font-semibold">{title}</span>{body && <span className="block text-sm text-mute">{body}</span>}</span>
    </label>
  );
}

/** One form for both kinds of event: a fest's events (days, registration, teams, questions) and standalone city events. */
export function EventForm({ kind, fest, event, copyOf = null, siblings = [], onSaved, onCancel }: {
  kind: "fest" | "city"; fest?: FestManage; event: ManagedEvent | FestEvent | null; copyOf?: ManagedEvent | null; siblings?: ManagedEvent[]; onSaved: () => void; onCancel: () => void;
}) {
  const isFest = kind === "fest";
  const base = event ?? copyOf;
  const days = useMemo(() => (fest?.start_date && fest.end_date ? Array.from({ length: fest.days_count ?? 1 }, (_, i) => ({ iso: addDays(fest.start_date as string, i), n: i + 1 })) : []), [fest?.start_date, fest?.end_date, fest?.days_count]);
  // A new fest event starts on the day of the last one added (or the fest's first day), so most of the form is already right
  const lastDate = siblings.length ? siblings[siblings.length - 1].date.slice(0, 10) : days[0]?.iso ?? "";
  const [f, setF] = useState<State>(event ? toState(event) : copyOf ? { ...toState(copyOf), title: `${copyOf.title} (copy)` } : { ...empty, date: isFest ? lastDate : "" });
  const [image, setImage] = useState<string | null>(base?.image_url ?? null);
  const [sections, setSections] = useState<ExtraSection[]>(base?.extra_sections ?? []);
  const [template, setTemplate] = useState<string | null>(null);
  const [duration, setDuration] = useState(120);
  const [endAuto, setEndAuto] = useState(!base);   // the end time follows the start time until it is typed by hand
  const [descHint, setDescHint] = useState("");
  const [questions, setQuestions] = useState<QuestionDraft[]>([]);
  const [loadedQuestions, setLoadedQuestions] = useState("[]");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [clashes, setClashes] = useState<{ id: number; title: string; time: string | null; end_time: string | null }[]>([]);
  const venues = Array.from(new Set(siblings.map((e) => e.location).filter(Boolean) as string[]));
  const set = <K extends keyof State>(k: K, v: State[K]) => setF((x) => ({ ...x, [k]: v }));
  const registered = event && "registration_count" in event ? event.registration_count : 0;
  const locked = registered > 0;

  // Whether this fest has visiting colleges competing, and its usual points for 1st, 2nd, 3rd (only suggestions)
  const [competing, setCompeting] = useState(false);
  const [usualPoints, setUsualPoints] = useState<number[]>([100, 60, 30]);
  useEffect(() => {
    if (!isFest || !fest) return;
    api<{ enabled: boolean }>(`/api/fests/${fest.slug}/contingents/settings`).then((s) => setCompeting(s.enabled)).catch(() => {});
    api<{ default_placing_points: number[] }>(`/api/fests/${fest.slug}/competition/settings`).then((s) => setUsualPoints(s.default_placing_points)).catch(() => {});
  }, [isFest, fest]);
  const showPoints = isFest && (competing || f.scored);
  const showVisitors = isFest && (competing || f.entries);
  // Section numbers follow what is shown, so there are never gaps
  const nPoints = 6, nVisit = showPoints ? 7 : 6, nDetails = 6 + (showPoints ? 1 : 0) + (showVisitors ? 1 : 0);
  const turnScoring = (on: boolean) => setF((x) => ({ ...x, scored: on, points: on && x.points.length === 0 ? usualPoints.map(String) : x.points }));

  // Which days this event can start on, and how many days it can run from there (it cannot run past the end of the fest)
  const startIndex = days.findIndex((d) => d.iso === f.date);
  const outsideFest = isFest && days.length > 0 && !!f.date && startIndex < 0;
  const room = startIndex >= 0 ? days.length - startIndex : Math.max(parseInt(f.span, 10) || 1, 1);
  const span = Math.min(Math.max(parseInt(f.span, 10) || 1, 1), Math.max(room, 1));
  const lastDay = f.date ? addDays(f.date, span - 1) : "";
  const timing = f.time ? `${formatTime(f.time)}${f.end_time ? `–${formatTime(f.end_time)}` : ""}` : "";

  useEffect(() => {
    const source = event ?? copyOf;
    if (!source || !isFest) return;
    // For a copy the questions are loaded as drafts but not marked as saved, so they are created with the new event
    api<Question[]>(`/api/events/${source.id}/questions`).then((qs) => { const d = qs.map(toDraft); setQuestions(d); if (event) setLoadedQuestions(JSON.stringify(toQuestionPayload(d))); }).catch(() => {});
  }, [event, copyOf, isFest]);

  // Warn, without blocking, when this event wants a venue another event already has at the same time
  useEffect(() => {
    if (!isFest || !fest || !f.date || !f.time || !f.location.trim()) { setClashes([]); return; }
    let live = true;
    const timer = window.setTimeout(() => {
      const q = new URLSearchParams({ day: f.date, time: f.time, location: f.location.trim(), span_days: String(span) });
      if (f.end_time) q.set("end_time", f.end_time);
      if (event?.id) q.set("exclude_event_id", String(event.id));
      api<{ clashes: typeof clashes }>(`/api/fests/${fest.slug}/schedule/check?${q}`).then((r) => { if (live) setClashes(r.clashes); }).catch(() => { if (live) setClashes([]); });
    }, 400);
    return () => { live = false; window.clearTimeout(timer); };
  }, [isFest, fest, f.date, f.time, f.end_time, f.location, span, event?.id]);

  const applyTemplate = (t: (typeof TEMPLATES)[number] | null) => {
    setTemplate(t?.key ?? "blank");
    setDescHint(t?.hint ?? "");
    if (!t) return;
    setDuration(t.minutes);
    setF((x) => {
      const time = x.time || t.set.time || "";
      return { ...x, ...STRUCTURE_RESET, ...t.set, time, end_time: endAuto || !x.end_time ? addMinutes(time, t.minutes) : x.end_time };
    });
    setEndAuto(true);
    // Headings for the usual extra information, ready to fill in. Ones already written are kept
    setSections((cur) => [...cur.filter((s) => s.body.trim() || s.title.trim()), ...t.sections.filter((title) => !cur.some((s) => s.title.trim().toLowerCase() === title.toLowerCase())).map((title) => ({ title, body: "" }))].slice(0, 10));
  };
  const changeStart = (time: string) => setF((x) => ({ ...x, time, end_time: endAuto && time ? addMinutes(time, duration) : x.end_time }));
  const changeDay = (iso: string) => setF((x) => {
    const idx = days.findIndex((d) => d.iso === iso);
    const left = idx >= 0 ? days.length - idx : 15;
    return { ...x, date: iso, span: String(Math.min(parseInt(x.span, 10) || 1, left)), deadline: x.deadline && x.deadline > addDays(iso, Math.min(parseInt(x.span, 10) || 1, left) - 1) ? "" : x.deadline, opens_on: x.opens_on && x.opens_on > addDays(iso, Math.min(parseInt(x.span, 10) || 1, left) - 1) ? "" : x.opens_on };
  });

  const applied = template && template !== "blank" ? [
    f.requires_registration ? "Register first" : "Just turn up",
    f.requires_registration ? (f.is_team_event ? `Teams of ${f.team_min}–${f.team_max}` : "Solo entries") : null,
    f.registration_limit ? `${f.registration_limit} ${f.is_team_event ? "teams" : "seats"}` : null,
    f.time && f.end_time ? `${formatTime(f.time)}–${formatTime(f.end_time)}` : null,
    f.category || null,
  ].filter(Boolean) as string[] : [];

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isFest && f.requires_registration && f.reg_mode === "scheduled") {
      if (!f.opens_on) { setError("Pick the day registration opens, or choose another option."); return; }
      if (f.deadline && f.opens_on > f.deadline) { setError("Registration cannot open after it closes. Change one of the two days."); return; }
    }
    setBusy(true); setError("");
    try {
      const payload = payloadOf({ ...f, span: String(span) }, image, sections, isFest);
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

  const heading = event ? "Edit event" : copyOf ? "New event from a copy" : isFest ? "New event" : "New city event";
  const cityDay = (
    <div className="grid gap-4 sm:grid-cols-3">
      <Field label="Date"><input className="field" type="date" required value={f.date} onChange={(e) => set("date", e.target.value)} /></Field>
      <Field label="Starts"><input className="field" type="time" value={f.time} onChange={(e) => changeStart(e.target.value)} /></Field>
      <Field label="Ends"><input className="field" type="time" value={f.end_time} onChange={(e) => { setEndAuto(false); set("end_time", e.target.value); }} /></Field>
    </div>
  );

  return (
    <form onSubmit={submit} className="card max-w-4xl space-y-8 p-6 sm:p-8">
      <h2 className="font-display text-xl font-bold tracking-tight">{heading}</h2>
      <ErrorNote>{error}</ErrorNote>
      {copyOf && <Notice tone="info">This is a copy of &ldquo;{copyOf.title}&rdquo;. Change the title, the day and anything else that is different, then add it.</Notice>}
      {!isFest && <Notice tone="info">City events are standalone events, not part of a fest. HiveOut reviews each one before it appears on the site.</Notice>}

      {/* 1. What is it */}
      <Section n={1} title="What is it?" hint={isFest && !event && !copyOf ? "Start from a template to fill in the usual settings, then change anything." : undefined}>
        {isFest && !event && !copyOf && (
          <fieldset>
            <legend className="sr-only">Event template</legend>
            <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Event template">
              {TEMPLATES.map((t) => (
                <button key={t.key} type="button" role="radio" aria-checked={template === t.key} onClick={() => applyTemplate(t)} className={`rounded-2xl p-3.5 text-left ring-1 transition ${template === t.key ? "bg-white ring-2 ring-ink" : "bg-white/60 ring-black/10 hover:ring-black/30"}`}>
                  <span className="block text-sm font-semibold">{t.label}</span><span className="block text-xs text-mute">{t.about}</span>
                </button>
              ))}
              <button type="button" role="radio" aria-checked={template === "blank"} onClick={() => applyTemplate(null)} className={`rounded-2xl p-3.5 text-left ring-1 transition ${template === "blank" ? "bg-white ring-2 ring-ink" : "bg-white/60 ring-black/10 hover:ring-black/30"}`}>
                <span className="block text-sm font-semibold">Start blank</span><span className="block text-xs text-mute">Fill in everything yourself</span>
              </button>
            </div>
            {applied.length > 0 && <p className="mt-3 text-sm"><span className="font-semibold">The template set:</span> {applied.join(" · ")}. <span className="text-mute">Change anything below.</span></p>}
          </fieldset>
        )}
        <Field label="Title"><input className="field" required value={f.title} onChange={(e) => set("title", e.target.value)} placeholder="e.g. Battle of Bands" /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Category"><select className="field" value={f.category} onChange={(e) => set("category", e.target.value)}><option value="">Select</option>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select></Field>
        </div>
        <Field label="Description" hint={isFest ? "Required" : undefined}><textarea className="field min-h-28" required={isFest} placeholder={descHint} value={f.description} onChange={(e) => set("description", e.target.value)} /></Field>
      </Section>

      {/* 2. When */}
      <Section n={2} title="When is it?" hint={isFest && days.length > 0 ? `Your fest runs for ${days.length} day${days.length === 1 ? "" : "s"}. Pick the day it starts, and how many days it runs.` : undefined}>
        {isFest && days.length > 0 ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Starts on">
                <select className="field" required value={f.date} onChange={(e) => changeDay(e.target.value)}>
                  {!f.date && <option value="">Pick a day</option>}
                  {outsideFest && <option value={f.date}>{formatDay(f.date)} (outside your fest)</option>}
                  {days.map((d) => <option key={d.iso} value={d.iso}>Day {d.n} · {formatDay(d.iso)}</option>)}
                </select>
              </Field>
              <Field label="Runs for" hint={days.length === 1 ? "Your fest is a single day." : undefined}>
                <select className="field" value={String(span)} disabled={days.length === 1} onChange={(e) => { set("span", e.target.value); if (f.deadline && f.deadline > addDays(f.date, Number(e.target.value) - 1)) set("deadline", ""); }}>
                  {Array.from({ length: Math.max(room, 1) }, (_, i) => <option key={i + 1} value={i + 1}>{i === 0 ? "1 day" : `${i + 1} days (until ${formatDay(addDays(f.date, i))})`}</option>)}
                </select>
              </Field>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={span > 1 ? "Every day, from" : "Starts at"}><input className="field" type="time" required value={f.time} onChange={(e) => changeStart(e.target.value)} /></Field>
              <Field label={span > 1 ? "Every day, until" : "Ends at"}><input className="field" type="time" required value={f.end_time} onChange={(e) => { setEndAuto(false); set("end_time", e.target.value); }} /></Field>
            </div>
            {f.date && f.time && <p className="rounded-2xl bg-wash px-4 py-3 text-sm" aria-live="polite"><span className="font-semibold">{span > 1 ? `${formatDay(f.date)} to ${formatDay(lastDay)}` : formatDay(f.date)}</span>{timing ? `, ${timing}${span > 1 ? " every day" : ""}` : ""}</p>}
          </>
        ) : isFest ? (
          <>
            <Notice tone="warn">Set your fest&apos;s dates in Fest details first, so events can be placed on its days. You can still pick a date below.</Notice>
            {cityDay}
          </>
        ) : cityDay}
      </Section>

      {/* 3. Where */}
      <Section n={3} title="Where is it?">
        <Field label="Venue"><input className="field" required={isFest} list="venue-suggestions" value={f.location} onChange={(e) => set("location", e.target.value)} placeholder="e.g. Main Auditorium" /><datalist id="venue-suggestions">{venues.map((v) => <option key={v} value={v} />)}</datalist></Field>
        {clashes.length > 0 && <Notice tone="warn"><strong>This clashes with another event at {f.location.trim()}:</strong> {clashes.map((c) => `${c.title} (${c.time ?? ""}${c.end_time ? `–${c.end_time}` : ""})`).join(", ")}. You can still save it, or pick another time or venue.</Notice>}
      </Section>

      {/* 4. How people take part */}
      {isFest && (
        <Section n={4} title="How do people take part?" hint="This decides whether students register, and whether they come alone or as a team.">
          <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="How people join">
            <Choice name="join" checked={!f.requires_registration} disabled={locked} onChange={() => set("requires_registration", false)} title="Just turn up" body="No registration. Anyone can walk in." />
            <Choice name="join" checked={f.requires_registration} disabled={locked} onChange={() => set("requires_registration", true)} title="Register first" body="Students register on HiveOut, and you see who is coming." />
          </div>
          {locked && <p className="text-xs text-mute">These settings are locked because people have already registered.</p>}

          {f.requires_registration && (
            <>
              <div className="space-y-2">
                <p className="text-sm font-semibold">Solo or team?</p>
                <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Solo or team">
                  <Choice name="who" checked={!f.is_team_event} disabled={locked} onChange={() => set("is_team_event", false)} title="Solo" body="Each person registers on their own." />
                  <Choice name="who" checked={f.is_team_event} disabled={locked} onChange={() => set("is_team_event", true)} title="Team" body="One person makes a team and shares a code; the others join it." />
                </div>
              </div>
              {f.is_team_event && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Smallest team" hint={locked ? "Can only go down now" : "People, including the leader"}><input className="field" type="number" min={1} max={50} required value={f.team_min} onChange={(e) => set("team_min", e.target.value)} /></Field>
                  <Field label="Largest team" hint={locked ? "Can only go up now" : undefined}><input className="field" type="number" min={2} max={50} required value={f.team_max} onChange={(e) => set("team_max", e.target.value)} /></Field>
                </div>
              )}
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={f.is_team_event ? "Most teams" : "Seat limit"} hint="Leave empty for no limit"><input className="field" type="number" min={1} value={f.registration_limit} onChange={(e) => set("registration_limit", e.target.value)} /></Field>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-semibold">When can people register?</p>
                {f.reg_mode === "closed" ? (
                  <Notice tone="warn">Registration is closed. Use <strong>Open registrations</strong> on the events list to start it again.</Notice>
                ) : (
                  <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="When registration opens">
                    <Choice name="regopen" checked={f.reg_mode === "open_now"} onChange={() => set("reg_mode", "open_now")} title="Open now" body="Students can register straight away." />
                    <Choice name="regopen" checked={f.reg_mode === "scheduled"} onChange={() => set("reg_mode", "scheduled")} title="On a date" body="It opens by itself on the day you pick." />
                    <Choice name="regopen" checked={f.reg_mode === "not_set"} onChange={() => set("reg_mode", "not_set")} title="Not decided yet" body="Students see it is not open yet. Open it any time." />
                  </div>
                )}
                <div className="grid gap-4 sm:grid-cols-2">
                  {f.reg_mode === "scheduled" && (
                    <Field label="Registration opens on"><input className="field" type="date" required value={f.opens_on} max={(f.deadline && f.deadline < lastDay ? f.deadline : lastDay) || undefined} onChange={(e) => set("opens_on", e.target.value)} /></Field>
                  )}
                  <Field label="Registration closes on" hint={`Optional. Leave empty to keep it open until the event ends${lastDay ? ` (${formatDay(lastDay)})` : ""}.`}><input className="field" type="date" min={f.reg_mode === "scheduled" && f.opens_on ? f.opens_on : undefined} max={lastDay || undefined} value={f.deadline} onChange={(e) => set("deadline", e.target.value)} /></Field>
                </div>
                <p className="rounded-2xl bg-wash px-4 py-3 text-sm" aria-live="polite"><span className="font-semibold">Students will see:</span> {f.reg_mode === "closed" ? "Registration closed" : f.reg_mode === "open_now" ? "Registration is open" : f.reg_mode === "scheduled" ? (f.opens_on ? `Registration opens on ${formatDay(f.opens_on)}` : "Registration opens soon, once you pick a day") : "Registration is not open yet"}{f.deadline ? `, closes on ${formatDay(f.deadline)}` : ""}.</p>
              </div>
              <div className="space-y-2">
                <p className="text-sm font-semibold">Who confirms a registration?</p>
                <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Approval">
                  <Choice name="approval" checked={f.approval_mode === "auto"} onChange={() => set("approval_mode", "auto")} title="Confirmed instantly" body="Fastest for students." />
                  <Choice name="approval" checked={f.approval_mode === "manual"} onChange={() => set("approval_mode", "manual")} title="You approve each one" body={`Your committee approves each ${f.is_team_event ? "team" : "registration"}.`} />
                </div>
              </div>
            </>
          )}

          <div className="space-y-2">
            <p className="text-sm font-semibold">Who can take part?</p>
            <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Who can take part">
              <Choice name="eligible" checked={!f.students_only} onChange={() => set("students_only", false)} title="Anyone" body="Any HiveOut member." />
              <Choice name="eligible" checked={f.students_only} onChange={() => set("students_only", true)} title="Verified students only" body="Students who have verified their college." />
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-semibold">Entry fee</p>
            <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Entry fee">
              <Choice name="fee" checked={!f.paid} disabled={locked} onChange={() => set("paid", false)} title="Free" />
              <Choice name="fee" checked={f.paid} disabled={locked} onChange={() => set("paid", true)} title="Paid" body="Students pay to take part." />
            </div>
            {f.paid && (
              <div className="grid gap-4 pt-2 sm:grid-cols-2">
                <Field label="Price (₹)"><input className="field" type="number" min={1} required value={f.price} onChange={(e) => set("price", e.target.value)} /></Field>
                <Field label="Student price (₹)" hint="Optional. Lower than the price, for verified students."><input className="field" type="number" min={0} disabled={locked} value={f.student_price} onChange={(e) => set("student_price", e.target.value)} /></Field>
              </div>
            )}
            {f.paid && <Notice tone="warn">Online payment is not live yet. Students who register for a paid event are marked as paid without being charged, so collect the money yourselves for now.</Notice>}
          </div>
        </Section>
      )}

      {!isFest && (
        <Section n={4} title="Who can come?">
          <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Who can come">
            <Choice name="eligible" checked={!f.students_only} onChange={() => set("students_only", false)} title="Anyone" />
            <Choice name="eligible" checked={f.students_only} onChange={() => set("students_only", true)} title="Verified students only" />
          </div>
          <div className="space-y-2">
            <p className="text-sm font-semibold">Entry fee</p>
            <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Entry fee">
              <Choice name="fee" checked={!f.paid} onChange={() => set("paid", false)} title="Free" />
              <Choice name="fee" checked={f.paid} onChange={() => set("paid", true)} title="Paid" />
            </div>
            {f.paid && <div className="grid gap-4 pt-2 sm:grid-cols-2">
              <Field label="Price (₹)"><input className="field" type="number" min={1} required value={f.price} onChange={(e) => set("price", e.target.value)} /></Field>
              <Field label="Student price (₹)" hint="Optional. Lower than the price, for verified students."><input className="field" type="number" min={0} value={f.student_price} onChange={(e) => set("student_price", e.target.value)} /></Field>
            </div>}
          </div>
        </Section>
      )}

      {/* 5. Who runs it */}
      {isFest && (
        <Section n={5} title="Who runs it?" hint="The person students can ask about this event. Shown on the event page.">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Coordinator's name"><input className="field" maxLength={120} value={f.coordinator_name} onChange={(e) => set("coordinator_name", e.target.value)} placeholder="e.g. Meera Shah" /></Field>
            <Field label="Coordinator's phone"><input className="field" type="tel" value={f.coordinator_phone} onChange={(e) => set("coordinator_phone", e.target.value)} placeholder="+91 98765 43210" /></Field>
          </div>
        </Section>
      )}

      {/* 6. A competition between colleges */}
      {showPoints && (
        <Section n={nPoints} title="Is it part of the competition between colleges?" hint="Visiting colleges earn points for placing in an event. You set how many, for this event only.">
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={f.scored} onChange={(e) => turnScoring(e.target.checked)} />
            <span><strong>Yes, contingents earn points here</strong><span className="block text-mute">After the event you record who placed where, and the points go onto each contingent.</span></span></label>
          {f.scored && (
            <div className="space-y-3">
              <p className="text-sm font-semibold">Points for each place</p>
              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
                {f.points.map((v, i) => (
                  <Field key={i} label={`${i + 1}${["st", "nd", "rd"][i] ?? "th"} place`}><input className="field" type="number" min={0} max={10000} value={v} onChange={(e) => set("points", f.points.map((x, j) => (j === i ? e.target.value : x)))} /></Field>
                ))}
              </div>
              <div className="flex gap-3 text-sm font-semibold">
                {f.points.length < 10 && <button type="button" onClick={() => set("points", [...f.points, "0"])} className="underline underline-offset-4">Add a place</button>}
                {f.points.length > 1 && <button type="button" onClick={() => set("points", f.points.slice(0, -1))} className="text-red-600 underline underline-offset-4">Remove the last</button>}
                <button type="button" onClick={() => set("points", usualPoints.map(String))} className="text-mute underline underline-offset-4">Use the usual points</button>
              </div>
            </div>
          )}
        </Section>
      )}

      {/* Visiting colleges entering the event */}
      {showVisitors && (
        <Section n={nVisit} title="Can visiting colleges enter it?" hint="Colleges send their own people, chosen from their list, from their own page.">
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={f.entries} onChange={(e) => set("entries", e.target.checked)} />
            <span><strong>Yes, open it to visiting colleges</strong><span className="block text-mute">{f.is_team_event ? `Each entry is a team of ${f.team_min}–${f.team_max} people.` : "Each entry is one person."} You see every entry, and can enter or remove a college yourself.</span></span></label>
          {f.entries && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Entries each college may send" hint="For example 2 teams, or 3 singers"><input className="field" type="number" min={1} max={50} value={f.entries_per} onChange={(e) => set("entries_per", e.target.value)} /></Field>
              <Field label="Entries close on" hint={`Optional. Leave empty to keep them open until the event${lastDay ? ` (${formatDay(lastDay)})` : ""}.`}><input className="field" type="date" max={lastDay || undefined} value={f.entry_deadline} onChange={(e) => set("entry_deadline", e.target.value)} /></Field>
              <Field label="Entry fee (₹)" hint="Leave empty if free. It is added to the college's fees."><input className="field" type="number" min={0} step="0.01" value={f.entry_fee} onChange={(e) => set("entry_fee", e.target.value)} /></Field>
              <Field label="The fee is charged"><select className="field" value={f.entry_fee_per} onChange={(e) => set("entry_fee_per", e.target.value as "entry" | "participant")}><option value="entry">For each entry</option><option value="participant">For each person taking part</option></select></Field>
            </div>
          )}
        </Section>
      )}

      {/* Details */}
      <Section n={isFest ? nDetails : 5} title="Rules, prizes and a picture" hint="Shown on the event page.">
        <SectionsEditor value={sections} onChange={setSections} hint="Rules, prizes, eligibility: whatever people should know before they join." />
        <ImageUpload kind="cover" value={image} onChange={setImage} />
      </Section>

      {isFest && f.requires_registration && (
        <Section n={nDetails + 1} title="Questions for people who register" hint="Anything you need to know from each registration, such as their college or a team name."><QuestionsEditor value={questions} onChange={setQuestions} locked={locked} /></Section>
      )}

      <div className="flex gap-3 border-t border-black/5 pt-6">
        <Button type="submit" size="lg" disabled={busy || (isFest && days.length > 0 && !f.date)}>{busy ? "Saving…" : event ? "Save changes" : isFest ? "Add event" : "Submit for approval"}</Button>
        <Button type="button" size="lg" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}
