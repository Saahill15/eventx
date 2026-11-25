"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { College, ContingentDetail, ContingentMember, ContingentSettings, ContingentStatus, Fest } from "@/lib/types";
import { formatDay } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";

const TONE: Record<ContingentStatus, "amber" | "green" | "red" | "neutral"> = { pending: "amber", approved: "green", rejected: "red", withdrawn: "neutral" };

function RegisterForm({ slug, fest, s, onDone }: { slug: string; fest: Fest; s: ContingentSettings; onDone: () => void }) {
  const [colleges, setColleges] = useState<College[]>([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { api<College[]>("/api/colleges/").then(setColleges).catch(() => {}); }, []);
  const term = s.term.toLowerCase();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    const listed = colleges.find((c) => c.name.toLowerCase() === name.trim().toLowerCase());
    try { await api(`/api/fests/${slug}/contingents`, { method: "POST", body: { college_name: name.trim(), college_id: listed?.id ?? null } }); onDone(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not register."); setBusy(false); }
  };

  return (
    <form onSubmit={submit} className="card max-w-xl space-y-5 p-6 sm:p-8">
      <div><h2 className="font-display text-2xl font-bold tracking-tight">Register your college</h2><p className="mt-1 text-mute">Bring your college to {fest.name}. You will be its {s.leader_term.toLowerCase()}, and you can add up to {s.max_assistants} {s.assistant_term.toLowerCase()}{s.max_assistants === 1 ? "" : "s"} to help.</p></div>
      <ErrorNote>{error}</ErrorNote>
      <Field label="Your college" hint={s.requires_approval ? `The committee reviews each ${term} before it is confirmed.` : undefined}>
        <input className="field" required autoFocus list="college-list" minLength={2} maxLength={200} value={name} onChange={(e) => setName(e.target.value)} placeholder="Start typing, or enter the full name" />
        <datalist id="college-list">{colleges.map((c) => <option key={c.id} value={c.name} />)}</datalist>
      </Field>
      <p className="text-sm text-mute">Team size: {s.min_members}{s.max_members ? `–${s.max_members}` : " or more"} people{s.closes_on ? ` · registration closes ${formatDay(s.closes_on)}` : ""}.</p>
      <Button type="submit" size="lg" disabled={busy || name.trim().length < 2}>{busy ? "Registering…" : `Register ${term}`}</Button>
    </form>
  );
}

function MemberForm({ initial, busy, onSave, onCancel, label }: { initial?: ContingentMember; busy: boolean; onSave: (b: Record<string, unknown>) => void; onCancel?: () => void; label: string }) {
  const [f, setF] = useState({ name: initial?.name ?? "", email: initial?.email ?? "", phone: initial?.phone ?? "", year: initial?.year ? String(initial.year) : "", notes: initial?.notes ?? "" });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF((x) => ({ ...x, [k]: e.target.value }));
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({ name: f.name.trim(), email: f.email.trim() || null, phone: f.phone.trim() || null, year: f.year ? Number(f.year) : null, notes: f.notes.trim() || null });
    if (!initial) setF({ name: "", email: "", phone: "", year: "", notes: "" });
  };
  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-[1.4fr_1.4fr_1fr_80px_auto] sm:items-end">
      <Field label="Name"><input className="field" required maxLength={120} value={f.name} onChange={set("name")} /></Field>
      <Field label="Email (optional)"><input className="field" type="email" value={f.email} onChange={set("email")} /></Field>
      <Field label="Phone (optional)"><input className="field" type="tel" value={f.phone} onChange={set("phone")} placeholder="+91 98765 43210" /></Field>
      <Field label="Year"><input className="field" type="number" min={1} max={10} value={f.year} onChange={set("year")} /></Field>
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy || !f.name.trim()}>{label}</Button>{onCancel && <Button size="sm" type="button" variant="ghost" onClick={onCancel}>Cancel</Button>}</div>
    </form>
  );
}

function Dashboard({ slug, fest, s, c, reload, onRegisterAgain }: { slug: string; fest: Fest; s: ContingentSettings; c: ContingentDetail; reload: () => void; onRegisterAgain: () => void }) {
  const { user } = useAuth();
  const [email, setEmail] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [college, setCollege] = useState(c.college_name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const term = s.term.toLowerCase();
  const isLeader = c.my_role === "leader";
  const active = c.status === "pending" || c.status === "approved";
  const canEditRoster = active && c.roster_open;
  const base = `/api/fests/${slug}/contingents/${c.id}`;

  const act = async (fn: () => Promise<unknown>, ok?: string) => {
    setBusy(true); setError(""); setNotice("");
    try { await fn(); if (ok) setNotice(ok); reload(); } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); }
    setBusy(false);
  };

  return (
    <div className="max-w-4xl space-y-6">
      <section className="card space-y-3 p-6 sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-chip-ink">{fest.name}</p>
            <h2 className="mt-1 font-display text-3xl font-bold tracking-tight">{c.college_name}</h2></div>
          <Pill tone={TONE[c.status]}>{c.status === "pending" ? "Waiting for approval" : c.status === "approved" ? "Approved" : c.status === "rejected" ? "Not approved" : "Withdrawn"}</Pill>
        </div>
        {c.status === "pending" && <Notice tone="info">The committee has your registration and will confirm it. You can already add your helpers and your people.</Notice>}
        {c.status === "approved" && <Notice tone="ok">You are in. {c.note ? c.note : ""}</Notice>}
        {c.status === "rejected" && <Notice tone="warn"><strong>The committee did not approve this.</strong> {c.note}</Notice>}
        {(c.code || c.name) && (
          <dl className="grid gap-3 rounded-2xl bg-wash p-4 text-sm sm:grid-cols-2">
            {c.name && <div><dt className="text-xs font-semibold uppercase tracking-wider text-mute">Your {term} name</dt><dd className="font-display text-xl font-bold">{c.name}</dd></div>}
            {c.code && <div><dt className="text-xs font-semibold uppercase tracking-wider text-mute">Code</dt><dd className="font-display text-xl font-bold">{c.code}</dd></div>}
          </dl>
        )}
        <ErrorNote>{error}</ErrorNote>
        {notice && <Notice tone="ok">{notice}</Notice>}
        {isLeader && active && (renaming ? (
          <form onSubmit={(e) => { e.preventDefault(); act(() => api(base, { method: "PATCH", body: { college_name: college.trim() } }), "College updated.").then(() => setRenaming(false)); }} className="flex flex-wrap items-end gap-3">
            <div className="min-w-[16rem] flex-1"><Field label="College name"><input className="field" required minLength={2} maxLength={200} value={college} onChange={(e) => setCollege(e.target.value)} /></Field></div>
            <Button size="sm" type="submit" disabled={busy}>Save</Button><Button size="sm" type="button" variant="ghost" onClick={() => { setRenaming(false); setCollege(c.college_name); }}>Cancel</Button>
          </form>
        ) : <button onClick={() => setRenaming(true)} className="text-sm font-semibold underline underline-offset-4">Correct the college name</button>)}
        {c.status === "rejected" && <div><Button onClick={onRegisterAgain}>Register again</Button></div>}
      </section>

      {active && (
        <section className="card space-y-4 p-6 sm:p-8" aria-label="Helpers">
          <div><h3 className="font-display text-xl font-bold tracking-tight">{s.assistant_term}s <span className="font-normal text-mute">({c.assistants.length} of {s.max_assistants})</span></h3><p className="mt-1 text-sm text-mute">They can manage your list of people. They need a HiveOut account.</p></div>
          {c.assistants.length > 0 && <ul className="divide-y divide-black/5">{c.assistants.map((a) => <li key={a.user_id} className="flex items-center justify-between gap-3 py-2 text-sm"><span><span className="font-medium">{a.user_name}</span> <span className="text-mute">{a.user_email}</span></span>{(isLeader || c.my_role === "staff") ? <button disabled={busy} onClick={() => act(() => api(`${base}/assistants/${a.user_id}`, { method: "DELETE" }))} className="font-semibold text-red-600 underline underline-offset-4">Remove</button> : null}</li>)}</ul>}
          {c.my_role === "assistant" && user && <p className="text-sm"><button disabled={busy} onClick={() => window.confirm(`Stop helping with the ${c.college_name} ${term}?`) && act(() => api(`${base}/assistants/${user.id}`, { method: "DELETE" }))} className="font-semibold text-red-600 underline underline-offset-4">Stop helping with this {term}</button></p>}
          {isLeader && c.assistants.length < s.max_assistants && (
            <form onSubmit={(e) => { e.preventDefault(); act(() => api(`${base}/assistants`, { method: "POST", body: { email: email.trim() } }), "Added. They have been told.").then(() => setEmail("")); }} className="flex flex-wrap items-end gap-3">
              <div className="min-w-[16rem] flex-1"><Field label={`Add your ${s.assistant_term.toLowerCase()} by email`}><input className="field" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Their HiveOut email" /></Field></div>
              <Button size="sm" type="submit" disabled={busy || !email.includes("@")}>Add</Button>
            </form>
          )}
        </section>
      )}

      <section className="card space-y-4 p-6 sm:p-8" aria-label="Your people">
        <div><h3 className="font-display text-xl font-bold tracking-tight">Your people <span className="font-normal text-mute">({c.member_count}{s.max_members ? ` of ${s.max_members}` : ""})</span></h3>
          <p className="mt-1 text-sm text-mute">Everyone you are bringing. They do not need accounts. The fest asks for {s.min_members}{s.max_members ? `–${s.max_members}` : " or more"} people.</p></div>
        {!c.roster_ok && active && <Notice tone="warn">You have {c.member_count} {c.member_count === 1 ? "person" : "people"}, and {fest.name} asks for {s.min_members}{s.max_members ? `–${s.max_members}` : " or more"}.</Notice>}
        {!c.roster_open && active && <Notice tone="info">Registration has closed, so the list is locked. Ask the committee if something needs to change.</Notice>}
        {c.members.length === 0 ? <p className="text-sm text-mute">Nobody added yet.</p> : (
          <ul className="divide-y divide-black/5 rounded-2xl bg-wash px-4">
            {c.members.map((m) => (
              <li key={m.id} className="py-3 text-sm">
                {editing === m.id ? <MemberForm initial={m} busy={busy} label="Save" onCancel={() => setEditing(null)} onSave={(b) => act(() => api(`${base}/members/${m.id}`, { method: "PATCH", body: b })).then(() => setEditing(null))} /> : (
                  <div className="flex flex-wrap items-center justify-between gap-2"><span><span className="font-medium">{m.name}</span> <span className="text-mute">{[m.email, m.phone, m.year ? `year ${m.year}` : null].filter(Boolean).join(" · ")}</span></span>
                    {canEditRoster && <span className="flex gap-3"><button onClick={() => setEditing(m.id)} className="font-semibold underline underline-offset-4">Edit</button><button disabled={busy} onClick={() => act(() => api(`${base}/members/${m.id}`, { method: "DELETE" }))} className="font-semibold text-red-600 underline underline-offset-4">Remove</button></span>}</div>
                )}
              </li>
            ))}
          </ul>
        )}
        {canEditRoster && (s.max_members === null || c.member_count < s.max_members) && (
          <div className="border-t border-black/5 pt-4"><MemberForm busy={busy} label="Add" onSave={(b) => act(() => api(`${base}/members`, { method: "POST", body: b }))} /></div>
        )}
      </section>

      {isLeader && active && (
        <p className="text-sm"><button disabled={busy} onClick={() => window.confirm(`Withdraw ${c.college_name} from ${fest.name}? Your list and any ${term} name or code you were given are released.`) && act(() => api(`${base}/withdraw`, { method: "POST" }))} className="font-semibold text-red-600 underline underline-offset-4">Withdraw from {fest.name}</button></p>
      )}
    </div>
  );
}

/** The page a visiting college's leader uses: register the college, see its status and code, add helpers, manage the list of people. */
export function ContingentPortal({ slug }: { slug: string }) {
  const [fest, setFest] = useState<Fest | null>(null);
  const [s, setS] = useState<ContingentSettings | null>(null);
  const [mine, setMine] = useState<ContingentDetail | null | undefined>(undefined);
  const [registering, setRegistering] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [f, st, m] = await Promise.all([api<Fest>(`/api/fests/${slug}`), api<ContingentSettings>(`/api/fests/${slug}/contingents/settings`), api<ContingentDetail | null>(`/api/fests/${slug}/contingents/mine`)]);
      setFest(f); setS(st); setMine(m); setRegistering(false); setError("");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load this page."); setMine(null); }
  }, [slug]);
  useEffect(() => { load(); }, [load]);

  const shell = (children: React.ReactNode) => (
    <div className="mx-auto max-w-5xl px-5 pb-16 pt-10 sm:px-8 sm:pt-14">
      <Link href={`/fests/${slug}`} className="text-sm text-mute hover:text-ink">← {fest?.name ?? "Back to the fest"}</Link>
      <div className="mt-6">{children}</div>
    </div>
  );

  if (error) return shell(<div className="card max-w-xl p-8"><ErrorNote>{error}</ErrorNote></div>);
  if (!fest || !s || mine === undefined) return shell(<div className="space-y-4"><Skeleton className="h-10 w-64" /><Skeleton className="h-48" /></div>);
  if (mine && !registering) return shell(<Dashboard slug={slug} fest={fest} s={s} c={mine} reload={load} onRegisterAgain={() => setRegistering(true)} />);

  const term = s.term.toLowerCase();
  if (!s.enabled) return shell(<div className="card max-w-xl p-8"><h2 className="font-display text-2xl font-bold tracking-tight">Not taking other colleges</h2><p className="mt-2 text-mute">{fest.name} is not registering {term}s from other colleges. Check the fest page for how to take part.</p></div>);
  if (!s.registration_open) return shell(<div className="card max-w-xl p-8"><h2 className="font-display text-2xl font-bold tracking-tight">Registration is not open</h2><p className="mt-2 text-mute">{s.opens_on && new Date(s.opens_on) > new Date() ? `${fest.name} opens registration for ${term}s on ${formatDay(s.opens_on)}.` : `Registration for ${term}s at ${fest.name} has closed.`}</p></div>);
  return shell(<RegisterForm slug={slug} fest={fest} s={s} onDone={load} />);
}
