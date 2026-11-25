"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ManagedEvent, Org, Shift, ShiftCoverage } from "@/lib/types";
import { formatLongDay } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";

const USUAL = ["Main gate", "Registration desk", "Help desk", "Stage management", "Hospitality", "Parking", "First aid", "Cleanup"];
const hhmm = (iso: string) => { const d = new Date(iso); const h = d.getHours(); return `${h % 12 || 12}:${String(d.getMinutes()).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`; };
const dayOf = (iso: string) => iso.slice(0, 10);
const range = (s: Shift) => `${hhmm(s.starts_at)} to ${hhmm(s.ends_at)}`;

function useAct(after: () => void) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const act = useCallback(async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); after(); return true; } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); return false; } finally { setBusy(false); }
  }, [after]);
  return { act, error, busy };
}

function DutyForm({ slug, shift, org, events, festDays, onDone }: { slug: string; shift?: Shift; org: Org; events: ManagedEvent[]; festDays: string[]; onDone: () => void }) {
  const [f, setF] = useState({
    title: shift?.title ?? "", location: shift?.location ?? "", date: shift ? dayOf(shift.starts_at) : (festDays[0] ?? ""), from: shift ? shift.starts_at.slice(11, 16) : "09:00", to: shift ? shift.ends_at.slice(11, 16) : "13:00",
    needed: String(shift?.needed ?? 2), open: shift?.open_signup ?? false, notes: shift?.notes ?? "", event: shift?.event_id ? String(shift.event_id) : "", team: shift?.committee_team_id ? String(shift.committee_team_id) : "",
  });
  const [people, setPeople] = useState<number[]>([]);
  const [repeat, setRepeat] = useState<string[]>([]);
  const { act, error, busy } = useAct(onDone);
  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const body = { title: f.title, location: f.location || null, starts_at: `${f.date}T${f.from}:00`, ends_at: `${f.date}T${f.to}:00`, needed: Number(f.needed), open_signup: f.open, notes: f.notes || null, event_id: f.event ? Number(f.event) : null, committee_team_id: f.team ? Number(f.team) : null };
    act(() => api(shift ? `/api/fests/${slug}/shifts/${shift.id}` : `/api/fests/${slug}/shifts`, { method: shift ? "PATCH" : "POST", body: shift ? body : { ...body, member_ids: people, repeat_on: repeat } }));
  };
  const otherDays = festDays.filter((d) => d !== f.date);
  return (
    <form onSubmit={save} className="space-y-4 rounded-2xl bg-wash p-4">
      <ErrorNote>{error}</ErrorNote>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Duty"><input className="field" required maxLength={120} list="usual-duties" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="Main gate" /><datalist id="usual-duties">{USUAL.map((u) => <option key={u} value={u} />)}</datalist></Field>
        <Field label="Where" hint="Optional"><input className="field" maxLength={255} value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} placeholder="Gate 1" /></Field>
        <Field label="How many people"><input className="field" type="number" min={1} max={200} required value={f.needed} onChange={(e) => setF({ ...f, needed: e.target.value })} /></Field>
        <Field label="Day"><input className="field" type="date" required value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></Field>
        <Field label="From"><input className="field" type="time" required value={f.from} onChange={(e) => setF({ ...f, from: e.target.value })} /></Field>
        <Field label="To"><input className="field" type="time" required value={f.to} onChange={(e) => setF({ ...f, to: e.target.value })} /></Field>
        <Field label="For an event" hint="Optional"><select className="field" value={f.event} onChange={(e) => setF({ ...f, event: e.target.value })}><option value="">The whole fest</option>{events.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}</select></Field>
        <Field label="Team in charge" hint="Optional"><select className="field" value={f.team} onChange={(e) => setF({ ...f, team: e.target.value })}><option value="">None</option>{org.teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
        <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={f.open} onChange={(e) => setF({ ...f, open: e.target.checked })} />Members can put themselves down</label>
      </div>
      <Field label="Notes for whoever is on it" hint="Optional"><input className="field" maxLength={1000} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} placeholder="Bring your pass. Report to the gate lead." /></Field>
      {!shift && (
        <>
          <fieldset><legend className="mb-1 text-sm font-semibold">Put people on it now <span className="font-normal text-mute">(optional)</span></legend>
            <div className="grid gap-1.5 sm:grid-cols-3">{org.members.map((m) => <label key={m.id} className="flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-sm ring-1 ring-black/10"><input type="checkbox" checked={people.includes(m.id)} onChange={() => setPeople(toggle(people, m.id))} /><span className="truncate">{m.user_name}</span></label>)}</div></fieldset>
          {otherDays.length > 0 && (
            <fieldset><legend className="mb-1 text-sm font-semibold">Same hours on other days <span className="font-normal text-mute">(optional)</span></legend>
              <div className="flex flex-wrap gap-2">{otherDays.map((d) => <label key={d} className={`cursor-pointer rounded-full px-3.5 py-1.5 text-sm font-semibold ring-1 ${repeat.includes(d) ? "bg-ink text-white ring-ink" : "bg-white ring-black/10"}`}><input type="checkbox" className="sr-only" checked={repeat.includes(d)} onChange={() => setRepeat(toggle(repeat, d))} />{formatLongDay(`${d}T00:00:00`).replace(/,? \d{4}$/, "")}</label>)}</div></fieldset>
          )}
        </>
      )}
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy || !f.title.trim() || !f.date}>{shift ? "Save" : repeat.length ? `Add on ${repeat.length + 1} days` : "Add the duty"}</Button><Button size="sm" type="button" variant="ghost" onClick={onDone}>Cancel</Button></div>
    </form>
  );
}

function DutyCard({ slug, s, canManage, org, events, festDays, reload }: { slug: string; s: Shift; canManage: boolean; org: Org; events: ManagedEvent[]; festDays: string[]; reload: () => void }) {
  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState("");
  const { act, error, busy } = useAct(reload);
  const base = `/api/fests/${slug}/shifts/${s.id}`;
  const free = org.members.filter((m) => !s.people.some((p) => p.member_id === m.id));
  const tone = s.filled >= s.needed ? "green" : s.filled === 0 ? "red" : "amber";
  if (editing) return <li className="card p-4"><DutyForm slug={slug} shift={s} org={org} events={events} festDays={festDays} onDone={() => { setEditing(false); reload(); }} /></li>;
  return (
    <li className={`card p-4 ${s.state === "over" ? "opacity-70" : ""} ${s.mine ? "ring-2 ring-ink/70" : ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 font-semibold">{s.title}{s.mine && <Pill tone="green">You</Pill>}{s.state === "now" && <Pill tone="amber">On now</Pill>}{s.open_signup && s.state !== "over" && <Pill tone="neutral">Open to sign up</Pill>}</p>
          <p className="mt-0.5 text-sm text-mute">{range(s)}{s.location ? ` · ${s.location}` : ""}{s.event_title ? ` · ${s.event_title}` : ""}{s.team_name ? ` · ${s.team_name}` : ""}</p>
          {s.notes && <p className="mt-1 text-[13px] text-mute">{s.notes}</p>}
        </div>
        <Pill tone={tone}>{s.filled} of {s.needed}</Pill>
      </div>
      {s.people.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2">{s.people.map((p) => (
          <li key={p.member_id} className="flex items-center gap-2 rounded-full bg-wash py-1 pl-3 pr-2 text-sm">
            <span>{p.user_name}{p.title ? <span className="text-mute"> · {p.title}</span> : null}</span>
            {p.arrived_at && <Pill tone="green">Here</Pill>}{p.no_show && <Pill tone="red">Did not come</Pill>}
            {canManage && (
              <span className="flex gap-1.5 text-[12px] font-semibold">
                {s.state !== "upcoming" && !p.arrived_at && <button disabled={busy} onClick={() => act(() => api(`${base}/attendance`, { method: "PUT", body: { marks: [{ member_id: p.member_id, status: "arrived" }] } }))} className="underline underline-offset-2">Here</button>}
                {s.state === "over" && !p.no_show && !p.arrived_at && <button disabled={busy} onClick={() => act(() => api(`${base}/attendance`, { method: "PUT", body: { marks: [{ member_id: p.member_id, status: "no_show" }] } }))} className="underline underline-offset-2">Did not come</button>}
                {s.state !== "over" && <button aria-label={`Take ${p.user_name} off`} disabled={busy} onClick={() => act(() => api(`${base}/people/${p.member_id}`, { method: "DELETE" }))} className="text-red-600">Remove</button>}
              </span>
            )}
          </li>
        ))}</ul>
      )}
      <ErrorNote>{error}</ErrorNote>
      <div className="mt-3 flex flex-wrap items-center gap-3 text-[13px] font-semibold">
        {s.can_arrive && <Button size="sm" disabled={busy} onClick={() => act(() => api(`${base}/arrive`, { method: "POST" }))}>I am here</Button>}
        {s.can_claim && <Button size="sm" disabled={busy} onClick={() => act(() => api(`${base}/claim`, { method: "POST" }))}>Take this duty</Button>}
        {s.can_leave && <button disabled={busy} onClick={() => window.confirm("Take yourself off this duty?") && act(() => api(`${base}/claim`, { method: "DELETE" }))} className="underline underline-offset-4">Leave this duty</button>}
        {canManage && s.state !== "over" && s.filled < s.needed && free.length > 0 && (
          <span className="flex items-center gap-2"><select aria-label="Put someone on it" className="field !h-9 !w-auto" value={adding} onChange={(e) => setAdding(e.target.value)}><option value="">Put someone on it…</option>{free.map((m) => <option key={m.id} value={m.id}>{m.user_name}</option>)}</select>
            {adding && <Button size="sm" disabled={busy} onClick={() => act(() => api(`${base}/assign`, { method: "POST", body: { member_id: Number(adding) } })).then(() => setAdding(""))}>Add</Button>}</span>
        )}
        {canManage && <button onClick={() => setEditing(true)} className="underline underline-offset-4">Edit</button>}
        {canManage && <button disabled={busy} onClick={() => window.confirm(`Delete "${s.title}"?${s.filled ? " The people on it are told." : ""}`) && act(() => api(base, { method: "DELETE" }))} className="text-red-600 hover:underline">Delete</button>}
      </div>
    </li>
  );
}

/**
 * The duty roster. The director and core team build it (a duty, its hours, how many people, optionally across several days) and put
 * people on it; every member sees it, takes duties that are open, and says "I am here". `mineOnly` is the volunteer's own page.
 */
export function ShiftsTab({ slug, canManage, festDays = [], view = "all" }: { slug: string; canManage: boolean; festDays?: string[]; view?: "all" | "mine" | "open" }) {
  const [rows, setRows] = useState<Shift[] | null>(null);
  const [when, setWhen] = useState<"upcoming" | "past">("upcoming");
  const [filter, setFilter] = useState<"all" | "mine" | "open" | "short">(view === "all" ? "all" : view);
  const [org, setOrg] = useState<Org>({ teams: [], members: [] });
  const [events, setEvents] = useState<ManagedEvent[]>([]);
  const [cov, setCov] = useState<ShiftCoverage | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api<Shift[]>(`/api/fests/${slug}/shifts?when=${when}`).then((r) => { setRows(r); setError(""); }).catch((e) => { setError(e instanceof Error ? e.message : "Could not load the roster."); setRows([]); });
    if (canManage) api<ShiftCoverage>(`/api/fests/${slug}/shifts/coverage`).then(setCov).catch(() => {});
  }, [slug, when, canManage]);
  useEffect(() => { setRows(null); load(); }, [load]);
  useEffect(() => {
    api<Org>(`/api/fests/${slug}/org`).then(setOrg).catch(() => {});
    if (canManage) api<ManagedEvent[]>(`/api/fests/${slug}/manage/events`).then(setEvents).catch(() => {});
  }, [slug, canManage]);

  const shown = useMemo(() => (rows ?? []).filter((s) => filter === "all" || (filter === "mine" && s.mine) || (filter === "open" && (s.can_claim || (s.open_signup && s.open_spots > 0))) || (filter === "short" && s.filled < s.needed)), [rows, filter]);
  const days = useMemo(() => { const m = new Map<string, Shift[]>(); shown.forEach((s) => m.set(dayOf(s.starts_at), [...(m.get(dayOf(s.starts_at)) ?? []), s])); return Array.from(m.entries()); }, [shown]);
  const chip = (id: typeof filter, label: string) => <button key={id} aria-pressed={filter === id} onClick={() => setFilter(id)} className={`rounded-full px-4 py-2 text-sm font-semibold transition ${filter === id ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)] hover:text-ink"}`}>{label}</button>;

  return (
    <div className="max-w-4xl space-y-5">
      {canManage && cov && cov.upcoming > 0 && (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="card p-4"><p className="text-sm text-mute">Duties coming up</p><p className="font-display text-3xl font-bold">{cov.upcoming}</p></div>
          <div className="card p-4"><p className="text-sm text-mute">Spots still empty</p><p className={`font-display text-3xl font-bold ${cov.open_spots ? "text-amber-700" : ""}`}>{cov.open_spots}</p><p className="text-[13px] text-mute">across {cov.understaffed} duties</p></div>
          <div className="card p-4"><p className="text-sm text-mute">Members with no duty</p><p className="font-display text-3xl font-bold">{cov.unassigned_people.length}</p>{cov.unassigned_people.length > 0 && <p className="truncate text-[13px] text-mute">{cov.unassigned_people.slice(0, 3).join(", ")}{cov.unassigned_people.length > 3 ? "…" : ""}</p>}</div>
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Which duties">
          {chip("all", "Everyone")}{chip("mine", "Mine")}{chip("open", "Open to take")}{canManage && chip("short", "Needs people")}
          {when === "past" ? <button onClick={() => setWhen("upcoming")} className="rounded-full px-4 py-2 text-sm font-semibold text-mute underline underline-offset-4">Back to upcoming</button> : <button onClick={() => setWhen("past")} className="rounded-full px-4 py-2 text-sm font-semibold text-mute underline underline-offset-4">Past duties</button>}
        </div>
        {canManage && <Button size="sm" onClick={() => setAdding(!adding)}>{adding ? "Close" : "Add a duty"}</Button>}
      </div>
      <ErrorNote>{error}</ErrorNote>
      {adding && <DutyForm slug={slug} org={org} events={events} festDays={festDays} onDone={() => { setAdding(false); load(); }} />}
      {rows === null ? <Skeleton className="h-40" /> : days.length === 0 ? (
        <EmptyState title={rows.length === 0 ? (when === "past" ? "No past duties" : "No duties yet") : "Nothing here"} body={rows.length === 0 ? (canManage ? "A duty is a place and hours where you need people: the main gate, the registration desk, the stage. Add them, say how many people each needs, and put people on them, or let members put themselves down." : "When the core team adds duties for the fest, they show up here. You will be told when you are put on one.") : "Try another filter."} />
      ) : days.map(([day, list]) => (
        <section key={day} aria-label={day}>
          <h2 className="mb-2 text-[15px] font-semibold">{formatLongDay(`${day}T00:00:00`)}</h2>
          <ul className="space-y-3">{list.map((s) => <DutyCard key={s.id} slug={slug} s={s} canManage={canManage} org={org} events={events} festDays={festDays} reload={load} />)}</ul>
        </section>
      ))}
      {!canManage && rows && rows.some((s) => s.mine && s.state !== "over") && <Notice tone="info">You can say &quot;I am here&quot; from 30 minutes before your duty starts.</Notice>}
    </div>
  );
}
