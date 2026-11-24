"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import type { FestMeetingDetail, FestMeetingSummary, Member, Org } from "@/lib/types";
import { formatDay, formatTime } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";

const dayOf = (iso: string) => iso.slice(0, 10);
const timeOf = (iso: string) => iso.slice(11, 16);
const label = (iso: string) => `${formatDay(iso)}, ${formatTime(timeOf(iso))}`;

function People({ members, picked, onChange }: { members: Member[]; picked: Set<number>; onChange: (s: Set<number>) => void }) {
  const toggle = (id: number) => { const next = new Set(picked); if (next.has(id)) next.delete(id); else next.add(id); onChange(next); };
  return (
    <fieldset>
      <legend className="mb-1.5 flex items-center justify-between gap-3 text-sm font-semibold"><span>Who is invited <span className="font-normal text-mute">({picked.size})</span></span>
        <span className="flex gap-3 text-xs"><button type="button" onClick={() => onChange(new Set(members.map((m) => m.id)))} className="underline underline-offset-4">Everyone</button><button type="button" onClick={() => onChange(new Set())} className="underline underline-offset-4">Nobody</button></span>
      </legend>
      <ul className="grid gap-1.5 sm:grid-cols-2">
        {members.map((m) => <li key={m.id}><label className="flex items-center gap-2.5 text-sm"><input type="checkbox" className="h-4 w-4 accent-[#111]" checked={picked.has(m.id)} onChange={() => toggle(m.id)} />{m.user_name}{m.title ? <span className="text-mute">, {m.title}</span> : null}</label></li>)}
      </ul>
    </fieldset>
  );
}

function MeetingForm({ slug, org, meeting, onDone }: { slug: string; org: Org; meeting: FestMeetingDetail | null; onDone: (saved: FestMeetingDetail | null) => void }) {
  const [title, setTitle] = useState(meeting?.title ?? "");
  const [day, setDay] = useState(meeting ? dayOf(meeting.starts_at) : "");
  const [time, setTime] = useState(meeting ? timeOf(meeting.starts_at) : "17:00");
  const [location, setLocation] = useState(meeting?.location ?? "");
  const [agenda, setAgenda] = useState(meeting?.agenda ?? "");
  const [picked, setPicked] = useState<Set<number>>(new Set(meeting ? meeting.attendees.map((a) => a.member_id) : org.members.map((m) => m.id)));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    const body = { title: title.trim(), starts_at: `${day}T${time}:00`, location: location.trim() || null, agenda: agenda.trim() || null, member_ids: [...picked] };
    try {
      onDone(await api<FestMeetingDetail>(meeting ? `/api/fests/${slug}/meetings/${meeting.id}` : `/api/fests/${slug}/meetings`, { method: meeting ? "PATCH" : "POST", body }));
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save the meeting."); setBusy(false); }
  };

  return (
    <form onSubmit={save} className="card max-w-3xl space-y-4 p-6 sm:p-7">
      <h2 className="font-display text-xl font-bold tracking-tight">{meeting ? "Edit meeting" : "New meeting"}</h2>
      <ErrorNote>{error}</ErrorNote>
      <Field label="Title"><input className="field" required autoFocus maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Core committee weekly" /></Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Date"><input className="field" type="date" required value={day} onChange={(e) => setDay(e.target.value)} /></Field>
        <Field label="Time"><input className="field" type="time" required value={time} onChange={(e) => setTime(e.target.value)} /></Field>
        <Field label="Where"><input className="field" maxLength={255} value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Room, or a meeting link" /></Field>
      </div>
      <Field label="Agenda (optional)"><textarea className="field min-h-24" maxLength={5000} value={agenda} onChange={(e) => setAgenda(e.target.value)} placeholder={"1. Budget\n2. Poster designs\n3. Volunteer recruitment"} /></Field>
      <People members={org.members} picked={picked} onChange={setPicked} />
      <p className="text-xs text-mute">The people invited are told in their notifications{meeting ? ", and anyone newly invited or any change of time or place is announced" : ""}.</p>
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy || !title.trim() || !day}>{busy ? "Saving…" : meeting ? "Save changes" : "Schedule it"}</Button><Button size="sm" type="button" variant="ghost" onClick={() => onDone(null)}>Cancel</Button></div>
    </form>
  );
}

function MeetingView({ slug, id, org, onBack }: { slug: string; id: number; org: Org; onBack: () => void }) {
  const [m, setM] = useState<FestMeetingDetail | null>(null);
  const [editing, setEditing] = useState(false);
  const [agenda, setAgenda] = useState("");
  const [minutes, setMinutes] = useState("");
  const [came, setCame] = useState<Set<number>>(new Set());
  const [action, setAction] = useState({ title: "", assignee: "", due: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const adopt = useCallback((d: FestMeetingDetail) => { setM(d); setAgenda(d.agenda ?? ""); setMinutes(d.minutes ?? ""); setCame(new Set(d.attendees.filter((a) => a.attended).map((a) => a.member_id))); }, []);
  const load = useCallback(() => { api<FestMeetingDetail>(`/api/fests/${slug}/meetings/${id}`).then(adopt).catch((e) => setError(e instanceof Error ? e.message : "Could not load the meeting.")); }, [slug, id, adopt]);
  useEffect(() => { load(); }, [load]);

  const act = async (what: string, fn: () => Promise<unknown>) => {
    setBusy(true); setError(""); setSaved("");
    try { const r = await fn(); if (r && typeof r === "object" && "attendees" in r) adopt(r as FestMeetingDetail); else load(); setSaved(what); } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); }
    setBusy(false);
  };
  const addAction = async (e: React.FormEvent) => {
    e.preventDefault();
    await act("Action item added", () => api(`/api/fests/${slug}/tasks`, { method: "POST", body: { title: action.title.trim(), meeting_id: id, assignee_member_id: action.assignee ? Number(action.assignee) : null, due_date: action.due || null } }));
    setAction({ title: "", assignee: "", due: "" });
  };

  if (!m) return error ? <ErrorNote>{error}</ErrorNote> : <Skeleton className="h-48" />;
  if (editing) return <MeetingForm slug={slug} org={org} meeting={m} onDone={(d) => { setEditing(false); if (d) adopt(d); }} />;
  const past = new Date(m.starts_at) < new Date();

  return (
    <div className="max-w-3xl space-y-5">
      <button onClick={onBack} className="text-sm text-mute hover:text-ink">← All meetings</button>
      <section className="card space-y-3 p-6 sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><h2 className="font-display text-2xl font-bold tracking-tight">{m.title}</h2><p className="mt-1 text-mute">{label(m.starts_at)}{m.location ? ` · ${m.location}` : ""}</p></div>
          <div className="flex items-center gap-3"><Pill tone={past ? "neutral" : "green"}>{past ? "Held" : "Upcoming"}</Pill><button onClick={() => setEditing(true)} className="text-sm font-semibold underline underline-offset-4">Edit</button>
            <button disabled={busy} onClick={() => window.confirm(`Cancel "${m.title}"? The people invited are told, and its action items stay on the task board.`) && api(`/api/fests/${slug}/meetings/${id}`, { method: "DELETE" }).then(onBack).catch((e) => setError(e instanceof Error ? e.message : "Could not cancel."))} className="text-sm font-semibold text-red-600 underline underline-offset-4">Cancel meeting</button></div>
        </div>
        <ErrorNote>{error}</ErrorNote>
        {saved && <Notice tone="ok">{saved}.</Notice>}
      </section>

      <section className="card space-y-3 p-6 sm:p-7"><h3 className="font-display text-lg font-semibold tracking-tight">Agenda</h3>
        <textarea className="field min-h-24" aria-label="Agenda" value={agenda} maxLength={5000} onChange={(e) => setAgenda(e.target.value)} placeholder="What will be discussed" />
        <div><Button size="sm" variant="outline" disabled={busy || agenda.trim() === (m.agenda ?? "")} onClick={() => act("Agenda saved", () => api(`/api/fests/${slug}/meetings/${id}`, { method: "PATCH", body: { agenda: agenda.trim() || null } }))}>Save agenda</Button></div>
      </section>

      <section className="card space-y-3 p-6 sm:p-7"><h3 className="font-display text-lg font-semibold tracking-tight">Who came <span className="font-normal text-mute">({came.size} of {m.invited_count})</span></h3>
        {m.attendees.length === 0 ? <p className="text-sm text-mute">Nobody was invited.</p> : (
          <ul className="grid gap-1.5 sm:grid-cols-2">{m.attendees.map((a) => <li key={a.member_id}><label className="flex items-center gap-2.5 text-sm"><input type="checkbox" className="h-4 w-4 accent-[#111]" checked={came.has(a.member_id)} onChange={() => setCame((s) => { const n = new Set(s); if (n.has(a.member_id)) n.delete(a.member_id); else n.add(a.member_id); return n; })} />{a.user_name}{a.title ? <span className="text-mute">, {a.title}</span> : null}</label></li>)}</ul>
        )}
        {m.attendees.length > 0 && <div><Button size="sm" variant="outline" disabled={busy} onClick={() => act("Attendance saved", () => api(`/api/fests/${slug}/meetings/${id}/attendance`, { method: "PUT", body: { attended_member_ids: [...came] } }))}>Save attendance</Button></div>}
      </section>

      <section className="card space-y-3 p-6 sm:p-7"><h3 className="font-display text-lg font-semibold tracking-tight">Minutes</h3>
        <textarea className="field min-h-32" aria-label="Minutes" value={minutes} maxLength={20000} onChange={(e) => setMinutes(e.target.value)} placeholder="What was decided" />
        <div><Button size="sm" variant="outline" disabled={busy || minutes.trim() === (m.minutes ?? "")} onClick={() => act("Minutes saved", () => api(`/api/fests/${slug}/meetings/${id}`, { method: "PATCH", body: { minutes: minutes.trim() || null } }))}>Save minutes</Button></div>
      </section>

      <section className="card space-y-4 p-6 sm:p-7"><h3 className="font-display text-lg font-semibold tracking-tight">Action items <span className="font-normal text-mute">({m.open_action_count} open of {m.action_count})</span></h3>
        {m.actions.length === 0 ? <p className="text-sm text-mute">Nothing yet. Add what people agreed to do, and it goes onto the task board.</p> : (
          <ul className="divide-y divide-black/10">{m.actions.map((t) => <li key={t.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm"><span className={`font-medium ${t.status === "done" ? "text-mute line-through" : ""}`}>{t.title}</span><span className="text-mute">{t.assignee_name ?? "Unassigned"}{t.due_date ? ` · due ${formatDay(t.due_date)}` : ""} · {t.status === "done" ? "done" : t.status === "doing" ? "in progress" : "to do"}</span></li>)}</ul>
        )}
        <form onSubmit={addAction} className="grid gap-3 border-t border-black/5 pt-4 sm:grid-cols-[1fr_180px_150px_auto] sm:items-end">
          <Field label="Add an action item"><input className="field" required maxLength={200} value={action.title} onChange={(e) => setAction((a) => ({ ...a, title: e.target.value }))} placeholder="e.g. Email the sponsor" /></Field>
          <Field label="Who"><select className="field" value={action.assignee} onChange={(e) => setAction((a) => ({ ...a, assignee: e.target.value }))}><option value="">Nobody yet</option>{org.members.map((x) => <option key={x.id} value={x.id}>{x.user_name}</option>)}</select></Field>
          <Field label="Due"><input className="field" type="date" value={action.due} onChange={(e) => setAction((a) => ({ ...a, due: e.target.value }))} /></Field>
          <Button size="sm" type="submit" disabled={busy || !action.title.trim()}>Add</Button>
        </form>
      </section>
    </div>
  );
}

/** Meetings: schedule one, share the agenda, record who came and what was decided, and turn the follow-ups into tasks. */
export function MeetingsTab({ slug }: { slug: string }) {
  const [view, setView] = useState<"list" | "new" | number>("list");
  const [when, setWhen] = useState<"upcoming" | "past">("upcoming");
  const [rows, setRows] = useState<FestMeetingSummary[] | null>(null);
  const [org, setOrg] = useState<Org>({ teams: [], members: [] });
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setRows(await api<FestMeetingSummary[]>(`/api/fests/${slug}/meetings?when=${when}`)); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load the meetings."); setRows([]); }
  }, [slug, when]);
  useEffect(() => { api<Org>(`/api/fests/${slug}/org`).then(setOrg).catch(() => {}); }, [slug]);
  useEffect(() => { setRows(null); load(); }, [load]);

  if (view === "new") return <MeetingForm slug={slug} org={org} meeting={null} onDone={(d) => { if (d) { setWhen("upcoming"); setView(d.id); } else setView("list"); }} />;
  if (typeof view === "number") return <MeetingView slug={slug} id={view} org={org} onBack={() => { setView("list"); load(); }} />;

  return (
    <div className="max-w-3xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2" role="group" aria-label="Which meetings">
          {(["upcoming", "past"] as const).map((w) => <button key={w} aria-pressed={when === w} onClick={() => setWhen(w)} className={`rounded-full px-4 py-2 text-sm font-semibold capitalize transition ${when === w ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)] hover:text-ink"}`}>{w}</button>)}
        </div>
        <Button size="sm" onClick={() => setView("new")}><Plus className="h-4 w-4" /> New meeting</Button>
      </div>
      <ErrorNote>{error}</ErrorNote>
      {rows === null ? <Skeleton className="h-32" /> : rows.length === 0 ? (
        <EmptyState title={when === "upcoming" ? "No meetings scheduled" : "No past meetings"} body={when === "upcoming" ? "Schedule one, share the agenda, and the people you invite are told." : "Meetings you have held show up here, with their minutes and action items."} action={when === "upcoming" ? <Button onClick={() => setView("new")}>Schedule a meeting</Button> : undefined} />
      ) : (
        <ul className="space-y-3">
          {rows.map((m) => (
            <li key={m.id} className="card flex flex-wrap items-center justify-between gap-3 p-5">
              <div className="min-w-0"><p className="font-semibold">{m.title}</p><p className="mt-0.5 text-sm text-mute">{label(m.starts_at)}{m.location ? ` · ${m.location}` : ""}</p>
                <p className="mt-1 text-xs text-mute">{m.invited_count} invited{when === "past" ? ` · ${m.attended_count} came` : ""}{m.action_count ? ` · ${m.open_action_count} of ${m.action_count} action items open` : ""}</p></div>
              <Button size="sm" variant="outline" onClick={() => setView(m.id)}>Open</Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
