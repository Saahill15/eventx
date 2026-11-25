"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { CertTemplate, Certificate, ManagedEvent, PromoCode, Signatory, WaitlistRow } from "@/lib/types";
import { formatDay, inr } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";

function useRun(after: () => void) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const run = useCallback(async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); after(); return true; } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); return false; } finally { setBusy(false); }
  }, [after]);
  return { run, error, busy };
}

// ─── waiting lists ───────────────────────────────────────────────────────────

/** Everyone queuing for a full event, in order. A seat that opens goes to the first; the committee can also let someone in now. */
export function WaitlistAdmin({ slug }: { slug: string }) {
  const [rows, setRows] = useState<WaitlistRow[] | null>(null);
  const [event, setEvent] = useState("");
  const load = useCallback(() => { api<WaitlistRow[]>(`/api/fests/${slug}/waitlist`).then(setRows).catch(() => setRows([])); }, [slug]);
  useEffect(() => { load(); }, [load]);
  const { run, error, busy } = useRun(load);
  if (!rows) return <Skeleton className="h-40" />;
  const events = Array.from(new Map(rows.map((r) => [r.event_id, r.event_title])).entries());
  const shown = rows.filter((r) => !event || String(r.event_id) === event);
  const waiting = shown.filter((r) => r.status === "waiting");
  const history = shown.filter((r) => r.status !== "waiting");
  if (rows.length === 0) return <EmptyState title="Nobody is on a waiting list" body="When an event with a seat limit fills up, students can join a waiting list (turn it on in the event's form). Everyone queuing shows up here, and a seat that opens goes to the first in line by itself." />;
  return (
    <div className="max-w-4xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-mute">The first in line gets any seat that opens, automatically. You can also let someone in now, even past the limit.</p>
        {events.length > 1 && <select aria-label="Event" className="field !h-10 !w-auto" value={event} onChange={(e) => setEvent(e.target.value)}><option value="">All events</option>{events.map(([id, title]) => <option key={id} value={id}>{title}</option>)}</select>}</div>
      <ErrorNote>{error}</ErrorNote>
      {waiting.length === 0 ? <p className="text-sm text-mute">Nobody is waiting right now.</p> : (
        <ul className="space-y-2">{waiting.map((r) => (
          <li key={r.id} className="card flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="min-w-0"><p className="font-semibold"><span className="mr-2 inline-flex h-7 w-7 items-center justify-center rounded-full bg-chip text-[13px]">{r.position}</span>{r.user_name}{r.team_name ? ` · team ${r.team_name}` : ""}</p>
              <p className="text-[13px] text-mute">{r.event_title} · {r.user_email}{r.ticket_tier_name ? ` · ${r.ticket_tier_name}` : ""}{r.promo_code ? ` · code ${r.promo_code}` : ""} · joined {formatDay(r.created_at.slice(0, 10))}</p></div>
            <div className="flex gap-3 text-[13px] font-semibold"><Button size="sm" disabled={busy} onClick={() => window.confirm(`Let ${r.user_name} in now?`) && run(() => api(`/api/fests/${slug}/waitlist/${r.id}/admit`, { method: "POST" }))}>Let in now</Button>
              <button disabled={busy} onClick={() => { const why = window.prompt("Take them off the list? Say why (optional, they will be told):"); if (why !== null) run(() => api(`/api/fests/${slug}/waitlist/${r.id}?reason=${encodeURIComponent(why)}`, { method: "DELETE" })); }} className="text-red-600 hover:underline">Remove</button></div>
          </li>
        ))}</ul>
      )}
      {history.length > 0 && (
        <details className="card p-4"><summary className="cursor-pointer text-sm font-semibold">Earlier ({history.length})</summary>
          <ul className="mt-3 divide-y divide-[var(--ws-border)] text-sm">{history.map((r) => <li key={r.id} className="flex flex-wrap justify-between gap-2 py-2"><span>{r.user_name} · {r.event_title}</span><span className="text-mute">{r.status === "promoted" ? "Got a seat" : r.status === "left" ? "Left the list" : `Taken off${r.note ? `: ${r.note}` : ""}`}</span></li>)}</ul></details>
      )}
    </div>
  );
}

// ─── promo codes ─────────────────────────────────────────────────────────────

const PROMO_STATUS: Record<string, { text: string; tone: "green" | "amber" | "red" | "neutral" }> = { live: { text: "Live", tone: "green" }, not_yet: { text: "Not started", tone: "amber" }, expired: { text: "Expired", tone: "neutral" }, used_up: { text: "Used up", tone: "red" }, off: { text: "Switched off", tone: "neutral" } };

function PromoForm({ slug, promo, events, onDone }: { slug: string; promo?: PromoCode; events: ManagedEvent[]; onDone: () => void }) {
  const [f, setF] = useState({ code: promo?.code ?? "", kind: promo?.kind ?? "percent", value: promo ? String(promo.value) : "", description: promo?.description ?? "", max: promo?.max_uses ? String(promo.max_uses) : "", per: String(promo?.per_user_limit ?? 1), from: promo?.valid_from ?? "", until: promo?.valid_until ?? "", students: promo?.students_only ?? false });
  const [only, setOnly] = useState<number[] | null>(promo?.event_ids ?? null);
  const { run, error, busy } = useRun(onDone);
  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const shared = { description: f.description || null, value: Number(f.value), max_uses: f.max ? Number(f.max) : null, per_user_limit: Number(f.per) || 1, valid_from: f.from || null, valid_until: f.until || null, students_only: f.students, event_ids: only && only.length ? only : null };
    run(() => api(promo ? `/api/fests/${slug}/promo-codes/${promo.id}` : `/api/fests/${slug}/promo-codes`, { method: promo ? "PATCH" : "POST", body: promo ? shared : { code: f.code, kind: f.kind, ...shared } }));
  };
  const toggle = (id: number) => setOnly((cur) => { const list = cur ?? []; return list.includes(id) ? list.filter((x) => x !== id) : [...list, id]; });
  return (
    <form onSubmit={save} className="space-y-3 rounded-2xl bg-wash p-4">
      <ErrorNote>{error}</ErrorNote>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Code" hint="Letters, numbers, - and _"><input className="field uppercase" required disabled={!!promo} minLength={3} maxLength={40} value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} placeholder="EARLYBIRD" /></Field>
        <Field label="Takes off"><select className="field" disabled={!!promo} value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value as "percent" | "flat" })}><option value="percent">A percentage</option><option value="flat">A fixed amount</option></select></Field>
        <Field label={f.kind === "percent" ? "Percent (1 to 100)" : "Amount (₹)"}><input className="field" type="number" required min={1} max={f.kind === "percent" ? 100 : undefined} step={f.kind === "percent" ? 1 : 0.01} value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} /></Field>
        <Field label="Total uses" hint="Empty for no limit"><input className="field" type="number" min={1} value={f.max} onChange={(e) => setF({ ...f, max: e.target.value })} /></Field>
        <Field label="Uses per person"><input className="field" type="number" min={1} value={f.per} onChange={(e) => setF({ ...f, per: e.target.value })} /></Field>
        <Field label="Note for yourselves"><input className="field" maxLength={200} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} placeholder="e.g. College newsletter" /></Field>
        <Field label="Works from" hint="Optional"><input className="field" type="date" value={f.from} onChange={(e) => setF({ ...f, from: e.target.value })} /></Field>
        <Field label="Works until" hint="Optional"><input className="field" type="date" min={f.from || undefined} value={f.until} onChange={(e) => setF({ ...f, until: e.target.value })} /></Field>
        <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={f.students} onChange={(e) => setF({ ...f, students: e.target.checked })} />Verified students only</label>
      </div>
      <fieldset>
        <legend className="mb-1 text-sm font-semibold">Which events? <span className="font-normal text-mute">(none ticked means every event)</span></legend>
        <div className="grid gap-1.5 sm:grid-cols-2">{events.filter((e) => e.requires_registration).map((e) => <label key={e.id} className="flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-sm ring-1 ring-black/10"><input type="checkbox" checked={!!only?.includes(e.id)} onChange={() => toggle(e.id)} /><span className="truncate">{e.title}</span></label>)}</div>
      </fieldset>
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy || !f.value || (!promo && f.code.trim().length < 3)}>{promo ? "Save" : "Create the code"}</Button><Button size="sm" type="button" variant="ghost" onClick={onDone}>Cancel</Button></div>
    </form>
  );
}

/** Promo codes: a percentage or a fixed amount off a paid ticket, with the committee's own limits. */
export function PromoAdmin({ slug }: { slug: string }) {
  const [codes, setCodes] = useState<PromoCode[] | null>(null);
  const [events, setEvents] = useState<ManagedEvent[]>([]);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const load = useCallback(() => { api<PromoCode[]>(`/api/fests/${slug}/promo-codes`).then(setCodes).catch(() => setCodes([])); }, [slug]);
  useEffect(() => { load(); api<ManagedEvent[]>(`/api/fests/${slug}/manage/events`).then(setEvents).catch(() => {}); }, [load, slug]);
  const { run, error, busy } = useRun(load);
  if (!codes) return <Skeleton className="h-40" />;
  return (
    <div className="max-w-4xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-mute">Students type a code when they register for a paid event, and the price drops. Codes can be limited to some events, some dates, verified students, or a number of uses.</p><Button size="sm" onClick={() => setEditing(editing === "new" ? null : "new")}>{editing === "new" ? "Close" : "New promo code"}</Button></div>
      <ErrorNote>{error}</ErrorNote>
      {editing === "new" && <PromoForm slug={slug} events={events} onDone={() => { setEditing(null); load(); }} />}
      {codes.length === 0 && editing !== "new" ? <EmptyState title="No promo codes yet" body="Make a code for an early-bird offer, a sponsor's guests or a college newsletter. You see how often each is used and how much it took off." /> : (
        <ul className="space-y-3">{codes.map((p) => {
          const s = PROMO_STATUS[p.status];
          return (
            <li key={p.id} className="card p-4">
              {editing === p.id ? <PromoForm slug={slug} promo={p} events={events} onDone={() => { setEditing(null); load(); }} /> : (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0"><p className="flex flex-wrap items-center gap-2"><code className="rounded-lg bg-wash px-2.5 py-1 font-mono text-[15px] font-bold tracking-wider">{p.code}</code><Pill tone={s.tone}>{s.text}</Pill>{p.students_only && <Pill tone="neutral">Students only</Pill>}</p>
                      <p className="mt-1 text-sm font-semibold">{p.kind === "percent" ? `${p.value}% off` : `${inr(p.value)} off`}<span className="font-normal text-mute"> · {p.event_ids ? `${p.event_ids.length} event${p.event_ids.length === 1 ? "" : "s"}` : "every event"} · {p.per_user_limit === 1 ? "once each" : `${p.per_user_limit} times each`}{p.valid_from ? ` · from ${formatDay(p.valid_from)}` : ""}{p.valid_until ? ` · until ${formatDay(p.valid_until)}` : ""}</span></p>
                      {p.description && <p className="text-[13px] text-mute">{p.description}</p>}</div>
                    <div className="text-right text-sm"><p className="font-semibold">{p.used}{p.max_uses ? ` of ${p.max_uses}` : ""} used</p><p className="text-[13px] text-mute">{inr(p.discount_given)} taken off</p></div>
                  </div>
                  <div className="mt-3 flex gap-4 text-[13px] font-semibold">
                    <button onClick={() => setEditing(p.id)} className="underline underline-offset-4">Edit</button>
                    <button disabled={busy} onClick={() => run(() => api(`/api/fests/${slug}/promo-codes/${p.id}`, { method: "PATCH", body: { active: !p.active } }))} className="underline underline-offset-4">{p.active ? "Switch off" : "Switch on"}</button>
                    <button disabled={busy} onClick={() => window.confirm(`Delete ${p.code}?`) && run(() => api(`/api/fests/${slug}/promo-codes/${p.id}`, { method: "DELETE" }))} className="text-red-600 hover:underline">Delete</button>
                  </div>
                </>
              )}
            </li>
          );
        })}</ul>
      )}
    </div>
  );
}

// ─── certificates ────────────────────────────────────────────────────────────

const KIND: Record<string, string> = { participation: "Participation", winner: "Winner", appreciation: "Appreciation" };

function TemplateForm({ slug, t, events, onDone }: { slug: string; t?: CertTemplate; events: ManagedEvent[]; onDone: () => void }) {
  const [f, setF] = useState({ kind: t?.kind ?? "participation", title: t?.title ?? "", body: t?.body ?? "", event: t?.event_id ? String(t.event_id) : "" });
  const [sigs, setSigs] = useState<Signatory[]>(t?.signatories?.length ? t.signatories : [{ name: "", title: "" }]);
  const { run, error, busy } = useRun(onDone);
  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const body = { kind: f.kind, title: f.title, body: f.body, event_id: f.event ? Number(f.event) : null, signatories: sigs.filter((s) => s.name.trim()) };
    run(() => api(t ? `/api/fests/${slug}/certificate-templates/${t.id}` : `/api/fests/${slug}/certificate-templates`, { method: t ? "PATCH" : "POST", body }));
  };
  return (
    <form onSubmit={save} className="space-y-3 rounded-2xl bg-wash p-4">
      <ErrorNote>{error}</ErrorNote>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Kind"><select className="field" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value as CertTemplate["kind"] })}>{Object.entries(KIND).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        <Field label="Title on the certificate" ><input className="field" required maxLength={120} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="For"><select className="field" value={f.event} onChange={(e) => setF({ ...f, event: e.target.value })}><option value="">Any event</option>{events.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}</select></Field>
      </div>
      <Field label="Wording" hint="These fill in for each person: {name} {event} {fest} {college} {date} {award}"><textarea className="field min-h-24" required maxLength={1000} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} /></Field>
      <div className="space-y-2"><p className="text-sm font-semibold">Signed by <span className="font-normal text-mute">(up to three)</span></p>
        {sigs.map((s, i) => <div key={i} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]"><input aria-label="Name" className="field" placeholder="Name" maxLength={80} value={s.name} onChange={(e) => setSigs(sigs.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} /><input aria-label="Title" className="field" placeholder="Title, e.g. Principal" maxLength={80} value={s.title} onChange={(e) => setSigs(sigs.map((x, j) => j === i ? { ...x, title: e.target.value } : x))} /><button type="button" onClick={() => setSigs(sigs.filter((_, j) => j !== i))} className="text-[13px] font-semibold text-red-600 hover:underline">Remove</button></div>)}
        {sigs.length < 3 && <button type="button" onClick={() => setSigs([...sigs, { name: "", title: "" }])} className="text-[13px] font-semibold underline underline-offset-4">Add a signature</button>}</div>
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy || !f.title.trim() || !f.body.trim()}>{t ? "Save" : "Add wording"}</Button><Button size="sm" type="button" variant="ghost" onClick={onDone}>Cancel</Button></div>
    </form>
  );
}

/** Certificates: the committee's wording and signatures, issuing them to everyone who attended or one person at a time, and withdrawing a mistake. */
export function CertificatesAdmin({ slug }: { slug: string }) {
  const [templates, setTemplates] = useState<CertTemplate[] | null>(null);
  const [issued, setIssued] = useState<Certificate[]>([]);
  const [events, setEvents] = useState<ManagedEvent[]>([]);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [pick, setPick] = useState({ event: "", template: "" });
  const [one, setOne] = useState({ name: "", email: "", college: "", award: "" });
  const [message, setMessage] = useState("");
  const load = useCallback(() => {
    api<CertTemplate[]>(`/api/fests/${slug}/certificate-templates`).then(setTemplates).catch(() => setTemplates([]));
    api<Certificate[]>(`/api/fests/${slug}/certificates`).then(setIssued).catch(() => {});
  }, [slug]);
  useEffect(() => { load(); api<ManagedEvent[]>(`/api/fests/${slug}/manage/events`).then(setEvents).catch(() => {}); }, [load, slug]);
  const { run, error, busy } = useRun(load);
  if (!templates) return <Skeleton className="h-40" />;
  const usable = templates.filter((t) => !pick.event || t.event_id === null || String(t.event_id) === pick.event);
  const ready = pick.template && usable.some((t) => String(t.id) === pick.template);
  const bulk = (path: string) => run(async () => { const r = await api<{ issued: number; skipped: number }>(`/api/fests/${slug}/certificates/${path}`, { method: "POST", body: { event_id: Number(pick.event), template_id: Number(pick.template) } }); setMessage(`${r.issued} certificate${r.issued === 1 ? "" : "s"} issued${r.skipped ? `, ${r.skipped} already had one` : ""}.`); });

  return (
    <div className="max-w-4xl space-y-8">
      <ErrorNote>{error}</ErrorNote>
      <section className="space-y-3" aria-label="Wording">
        <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-[15px] font-semibold">Wording and signatures <span className="font-normal text-mute">{templates.length}</span></h2>
          <div className="flex gap-2">{templates.length < 3 && <Button size="sm" variant="outline" disabled={busy} onClick={() => run(() => api(`/api/fests/${slug}/certificate-templates/usual`, { method: "POST" }))}>Add the usual wordings</Button>}<Button size="sm" variant="outline" onClick={() => setEditing(editing === "new" ? null : "new")}>{editing === "new" ? "Close" : "Write your own"}</Button></div></div>
        {editing === "new" && <TemplateForm slug={slug} events={events} onDone={() => { setEditing(null); load(); }} />}
        {templates.length === 0 && editing !== "new" ? <p className="text-sm text-mute">No wording yet. Add the usual ones and change them, or write your own.</p> : (
          <ul className="space-y-2">{templates.map((t) => (
            <li key={t.id} className="card p-4">
              {editing === t.id ? <TemplateForm slug={slug} t={t} events={events} onDone={() => { setEditing(null); load(); }} /> : (
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0"><p className="flex flex-wrap items-center gap-2 font-semibold">{t.title}<Pill tone="neutral">{KIND[t.kind]}</Pill>{t.event_title && <Pill tone="amber">{t.event_title}</Pill>}</p><p className="mt-1 text-sm text-mute">{t.body}</p>{t.signatories.length > 0 && <p className="mt-1 text-[13px] text-mute">Signed by {t.signatories.map((s) => s.name).join(", ")}</p>}</div>
                  <div className="flex gap-3 text-[13px] font-semibold"><button onClick={() => setEditing(t.id)} className="underline underline-offset-4">Edit</button><button disabled={busy} onClick={() => window.confirm("Delete this wording? Certificates already issued keep theirs.") && run(() => api(`/api/fests/${slug}/certificate-templates/${t.id}`, { method: "DELETE" }))} className="text-red-600 hover:underline">Delete</button></div>
                </div>
              )}
            </li>
          ))}</ul>
        )}
      </section>

      <section className="card space-y-4 p-5" aria-label="Issue certificates">
        <div><h2 className="text-[15px] font-semibold">Issue certificates</h2><p className="text-sm text-mute">Pick an event and a wording. Each person gets one of each kind per event, so pressing a button twice does no harm.</p></div>
        {message && <Notice tone="ok">{message}</Notice>}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Event"><select className="field" value={pick.event} onChange={(e) => setPick({ event: e.target.value, template: "" })}><option value="">Choose an event</option>{events.filter((e) => !e.cancelled).map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}</select></Field>
          <Field label="Wording"><select className="field" value={pick.template} onChange={(e) => setPick({ ...pick, template: e.target.value })}><option value="">Choose a wording</option>{usable.map((t) => <option key={t.id} value={t.id}>{t.title} ({KIND[t.kind]})</option>)}</select></Field>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" disabled={busy || !pick.event || !ready} onClick={() => bulk("issue-attended")}>To everyone who attended</Button>
          <Button size="sm" variant="outline" disabled={busy || !pick.event || !ready} onClick={() => bulk("issue-entries")}>To visiting colleges&apos; entries</Button>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); run(() => api(`/api/fests/${slug}/certificates`, { method: "POST", body: { template_id: Number(pick.template), event_id: pick.event ? Number(pick.event) : null, recipient_name: one.name, email: one.email || null, college_name: one.college || null, award_text: one.award || null } })).then((ok) => { if (ok) { setMessage(`Issued to ${one.name}.`); setOne({ name: "", email: "", college: "", award: "" }); } }); }} className="space-y-3 border-t border-black/5 pt-4">
          <p className="text-sm font-semibold">Or to one person <span className="font-normal text-mute">(for example the winner)</span></p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Their name"><input className="field" required maxLength={120} value={one.name} onChange={(e) => setOne({ ...one, name: e.target.value })} /></Field>
            <Field label="Their college" hint="Optional"><input className="field" maxLength={200} value={one.college} onChange={(e) => setOne({ ...one, college: e.target.value })} /></Field>
            <Field label="What they won or did" hint="Fills {award}, e.g. First place"><input className="field" maxLength={120} value={one.award} onChange={(e) => setOne({ ...one, award: e.target.value })} /></Field>
            <Field label="Their HiveOut email" hint="Optional. Puts it on their page."><input className="field" type="email" value={one.email} onChange={(e) => setOne({ ...one, email: e.target.value })} /></Field>
          </div>
          <Button size="sm" variant="outline" type="submit" disabled={busy || !one.name.trim() || !pick.template}>Issue to this person</Button>
        </form>
      </section>

      <section className="space-y-3" aria-label="Issued">
        <h2 className="text-[15px] font-semibold">Issued <span className="font-normal text-mute">{issued.length}</span></h2>
        {issued.length === 0 ? <p className="text-sm text-mute">Nothing issued yet.</p> : (
          <ul className="space-y-2">{issued.map((c) => (
            <li key={c.id} className={`card flex flex-wrap items-center justify-between gap-3 p-4 ${c.revoked ? "opacity-60" : ""}`}>
              <div className="min-w-0"><p className="flex flex-wrap items-center gap-2 font-semibold">{c.recipient_name}{c.award_text && <Pill tone="green">{c.award_text}</Pill>}{c.revoked && <Pill tone="red">Withdrawn</Pill>}</p>
                <p className="text-[13px] text-mute">{c.title}{c.event_title ? ` · ${c.event_title}` : ""}{c.college_name ? ` · ${c.college_name}` : ""} · <code className="font-mono">{c.code}</code></p></div>
              <div className="flex gap-4 text-[13px] font-semibold"><Link href={`/certificates/${c.code}`} target="_blank" className="underline underline-offset-4">View and print</Link>
                {!c.revoked && <button disabled={busy} onClick={() => { const why = window.prompt("Withdraw this certificate? Say why:"); if (why && why.trim().length >= 3) run(() => api(`/api/fests/${slug}/certificates/${c.id}/revoke`, { method: "POST", body: { reason: why.trim() } })); }} className="text-red-600 hover:underline">Withdraw</button>}</div>
            </li>
          ))}</ul>
        )}
      </section>
    </div>
  );
}
