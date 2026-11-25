"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Contingent, ContingentDetail, ContingentSettings, ContingentStatus } from "@/lib/types";
import { formatDay } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";

const TONE: Record<ContingentStatus, "amber" | "green" | "red" | "neutral"> = { pending: "amber", approved: "green", rejected: "red", withdrawn: "neutral" };
const FILTERS: { id: ContingentStatus | "all"; label: string }[] = [{ id: "pending", label: "Waiting" }, { id: "approved", label: "Approved" }, { id: "rejected", label: "Not approved" }, { id: "withdrawn", label: "Withdrawn" }, { id: "all", label: "All" }];

function SettingsForm({ slug, settings, onSaved }: { slug: string; settings: ContingentSettings; onSaved: (s: ContingentSettings) => void }) {
  const [f, setF] = useState({ ...settings, max_members: settings.max_members === null ? "" : String(settings.max_members), opens_on: settings.opens_on ?? "", closes_on: settings.closes_on ?? "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => { setSaved(false); setF((x) => ({ ...x, [k]: v })); };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const out = await api<ContingentSettings>(`/api/fests/${slug}/contingents/settings`, { method: "PUT", body: {
        enabled: f.enabled, term: f.term, leader_term: f.leader_term, assistant_term: f.assistant_term, max_assistants: Number(f.max_assistants), min_members: Number(f.min_members),
        max_members: f.max_members === "" ? null : Number(f.max_members), allow_multiple_per_college: f.allow_multiple_per_college, requires_approval: f.requires_approval,
        opens_on: f.opens_on || null, closes_on: f.closes_on || null, lock_roster_after_close: f.lock_roster_after_close,
      } });
      setSaved(true); onSaved(out);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save."); }
    setBusy(false);
  };
  const check = (k: "allow_multiple_per_college" | "requires_approval" | "lock_roster_after_close", text: string, hint: string) => (
    <label className="flex items-start gap-3 text-sm"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-[#111]" checked={f[k]} onChange={(e) => set(k, e.target.checked)} /><span><span className="font-medium">{text}</span><span className="block text-mute">{hint}</span></span></label>
  );

  return (
    <form onSubmit={save} className="card space-y-5 p-6 sm:p-7">
      <ErrorNote>{error}</ErrorNote>
      <label className="flex items-start gap-3"><input type="checkbox" className="mt-1 h-4 w-4 accent-[#111]" checked={f.enabled} onChange={(e) => set("enabled", e.target.checked)} /><span><span className="font-semibold">Take visiting colleges at this fest</span><span className="block text-sm text-mute">Off by default. When on, other colleges can register from your fest page (while it is live and registration is open).</span></span></label>
      <fieldset className="space-y-4"><legend className="text-sm font-semibold">What do you call them?</legend>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="A visiting college's team"><input className="field" required maxLength={40} value={f.term} onChange={(e) => set("term", e.target.value)} /></Field>
          <Field label="Its leader"><input className="field" required maxLength={60} value={f.leader_term} onChange={(e) => set("leader_term", e.target.value)} /></Field>
          <Field label="The leader's helper"><input className="field" required maxLength={60} value={f.assistant_term} onChange={(e) => set("assistant_term", e.target.value)} /></Field>
        </div>
      </fieldset>
      <fieldset className="space-y-4"><legend className="text-sm font-semibold">Size</legend>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Helpers allowed"><input className="field" type="number" min={0} max={10} value={f.max_assistants} onChange={(e) => set("max_assistants", Number(e.target.value))} /></Field>
          <Field label="Smallest team"><input className="field" type="number" min={1} value={f.min_members} onChange={(e) => set("min_members", Number(e.target.value))} /></Field>
          <Field label="Largest team" hint="Empty for no limit"><input className="field" type="number" min={1} value={f.max_members} onChange={(e) => set("max_members", e.target.value)} /></Field>
        </div>
      </fieldset>
      <fieldset className="space-y-4"><legend className="text-sm font-semibold">Registration window <span className="font-normal text-mute">(optional)</span></legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Opens"><input className="field" type="date" value={f.opens_on} onChange={(e) => set("opens_on", e.target.value)} /></Field>
          <Field label="Closes"><input className="field" type="date" min={f.opens_on || undefined} value={f.closes_on} onChange={(e) => set("closes_on", e.target.value)} /></Field>
        </div>
      </fieldset>
      <div className="space-y-3">
        {check("requires_approval", "You approve each one", "Otherwise a college is approved the moment it registers.")}
        {check("allow_multiple_per_college", "A college can send more than one", "Otherwise a second registration from the same college is refused.")}
        {check("lock_roster_after_close", "Lock the roster once registration closes", "Colleges can no longer change their list of people; you still can.")}
      </div>
      <div className="flex items-center gap-3"><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save settings"}</Button>{saved && <span className="text-sm font-medium text-emerald-700">Saved</span>}</div>
    </form>
  );
}

function Row({ slug, c, settings, onChanged }: { slug: string; c: Contingent; settings: ContingentSettings; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const [d, setD] = useState<ContingentDetail | null>(null);
  const [note, setNote] = useState("");
  const [code, setCode] = useState(c.code ?? "");
  const [name, setName] = useState(c.name ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => { api<ContingentDetail>(`/api/fests/${slug}/contingents/${c.id}`).then((x) => { setD(x); setCode(x.code ?? ""); setName(x.name ?? ""); }).catch((e) => setError(e instanceof Error ? e.message : "Could not load.")); }, [slug, c.id]);
  useEffect(() => { if (open) load(); }, [open, load]);

  const act = async (fn: () => Promise<unknown>, done?: () => void) => {
    setBusy(true); setError("");
    try { await fn(); setNote(""); load(); onChanged(); done?.(); } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); }
    setBusy(false);
  };
  const post = (path: string, body?: unknown) => act(() => api(`/api/fests/${slug}/contingents/${c.id}/${path}`, { method: "POST", body }));

  return (
    <li className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 font-semibold">{c.college_name}<Pill tone={TONE[c.status]}>{FILTERS.find((x) => x.id === c.status)?.label ?? c.status}</Pill>{c.code && <Pill tone="neutral">{c.code}</Pill>}{c.name && <span className="font-normal text-mute">&ldquo;{c.name}&rdquo;</span>}</p>
          <p className="mt-0.5 text-sm text-mute">{c.leader_name} · {c.member_count} {c.member_count === 1 ? "person" : "people"}{c.assistant_count ? ` · ${c.assistant_count} ${c.assistant_count === 1 ? "helper" : "helpers"}` : ""} · registered {formatDay(c.created_at)}</p>
        </div>
        <Button size="sm" variant="outline" onClick={() => setOpen((v) => !v)}>{open ? "Hide" : "Open"}</Button>
      </div>

      {open && (
        <div className="mt-5 space-y-5 border-t border-black/5 pt-5">
          <ErrorNote>{error}</ErrorNote>
          {!d ? <Skeleton className="h-24" /> : (
            <>
              {d.note && <Notice tone="info"><strong>Your note:</strong> {d.note}</Notice>}
              {!d.roster_ok && d.status !== "rejected" && d.status !== "withdrawn" && <Notice tone="warn">The roster has {d.member_count} {d.member_count === 1 ? "person" : "people"}, outside the {settings.min_members}{settings.max_members ? `–${settings.max_members}` : "+"} this fest asks for.</Notice>}
              <dl className="grid gap-3 text-sm sm:grid-cols-2">
                <div><dt className="text-xs font-semibold uppercase tracking-wider text-mute">{settings.leader_term}</dt><dd>{d.leader_name} · {d.leader_email}</dd></div>
                <div><dt className="text-xs font-semibold uppercase tracking-wider text-mute">{settings.assistant_term}s</dt><dd>{d.assistants.length === 0 ? "None" : d.assistants.map((a) => `${a.user_name} (${a.user_email})`).join(", ")}</dd></div>
              </dl>
              <div>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-mute">Roster ({d.member_count})</p>
                {d.members.length === 0 ? <p className="text-sm text-mute">Nobody added yet.</p> : (
                  <ul className="divide-y divide-black/5 rounded-2xl bg-wash px-4 text-sm">{d.members.map((m) => <li key={m.id} className="flex flex-wrap justify-between gap-2 py-2"><span className="font-medium">{m.name}</span><span className="text-mute">{[m.email, m.phone, m.year ? `year ${m.year}` : null].filter(Boolean).join(" · ")}</span></li>)}</ul>
                )}
              </div>

              {(d.status === "pending" || d.status === "approved") && (
                <form onSubmit={(e) => { e.preventDefault(); act(() => api(`/api/fests/${slug}/contingents/${c.id}/assign`, { method: "PATCH", body: { code, name } })); }} className="grid gap-3 sm:grid-cols-[160px_1fr_auto] sm:items-end">
                  <Field label="Code"><input className="field" maxLength={30} value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. AL01" /></Field>
                  <Field label={`${settings.term} name`}><input className="field" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} placeholder="The name this college will carry" /></Field>
                  <Button size="sm" type="submit" disabled={busy || (code === (d.code ?? "") && name === (d.name ?? ""))}>Save</Button>
                </form>
              )}

              {d.status !== "withdrawn" && (
                <div className="space-y-3 border-t border-black/5 pt-4">
                  <Field label="Note for the leader" hint={d.status === "rejected" ? undefined : "Needed when you do not approve. Optional when you do."}><textarea className="field min-h-16" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
                  <div className="flex flex-wrap items-center gap-2">
                    {d.status !== "approved" && <Button size="sm" disabled={busy} onClick={() => post("approve", { note: note || null })}>Approve</Button>}
                    {d.status !== "rejected" && <Button size="sm" variant="outline" disabled={busy || note.trim().length < 5} onClick={() => post("reject", { note })}>Do not approve</Button>}
                    <Button size="sm" variant="ghost" disabled={busy} onClick={() => window.confirm(`Withdraw ${c.college_name}? Its code and name go back to the pool.`) && post("withdraw")}>Withdraw</Button>
                    <button disabled={busy} onClick={() => window.confirm(`Delete ${c.college_name} and its roster? This cannot be undone.`) && act(() => api(`/api/fests/${slug}/contingents/${c.id}`, { method: "DELETE" }))} className="ml-auto text-sm font-semibold text-red-600 underline underline-offset-4">Delete</button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </li>
  );

}

/** The committee's side of visiting colleges: turn it on, set the fest's own rules and words, and look after each college. */
export function ContingentsTab({ slug }: { slug: string }) {
  const [settings, setSettings] = useState<ContingentSettings | null>(null);
  const [rows, setRows] = useState<Contingent[] | null>(null);
  const [filter, setFilter] = useState<ContingentStatus | "all">("pending");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [s, list] = await Promise.all([api<ContingentSettings>(`/api/fests/${slug}/contingents/settings`), api<Contingent[]>(`/api/fests/${slug}/contingents`)]);
      setSettings(s); setRows(list); setError("");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load."); setRows([]); }
  }, [slug]);
  useEffect(() => { load(); }, [load]);

  if (settings === null) return error ? <ErrorNote>{error}</ErrorNote> : <Skeleton className="h-48" />;
  const counts = (id: ContingentStatus | "all") => (rows ?? []).filter((r) => id === "all" || r.status === id).length;
  const shown = (rows ?? []).filter((r) => filter === "all" || r.status === filter);
  const term = settings.term.toLowerCase();

  return (
    <div className="max-w-4xl space-y-6">
      <ErrorNote>{error}</ErrorNote>
      {!settings.enabled || editing ? (
        <div className="space-y-3">
          {!settings.enabled && <Notice tone="info">Visiting colleges are off for this fest. Turn them on below and set your own rules. Colleges register from your fest page once it is live.</Notice>}
          <SettingsForm slug={slug} settings={settings} onSaved={(s) => { setSettings(s); setEditing(false); }} />
        </div>
      ) : (
        <section className="card flex flex-wrap items-center justify-between gap-4 p-5" aria-label="Settings summary">
          <div className="text-sm"><p className="font-semibold">{settings.registration_open ? "Open for registration" : "Registration is not open"}</p>
            <p className="mt-0.5 text-mute">{settings.term} teams of {settings.min_members}{settings.max_members ? `–${settings.max_members}` : "+"} people · up to {settings.max_assistants} {settings.assistant_term.toLowerCase()}s · {settings.requires_approval ? "you approve each" : "approved automatically"}{settings.opens_on || settings.closes_on ? ` · ${settings.opens_on ? `opens ${formatDay(settings.opens_on)}` : ""}${settings.opens_on && settings.closes_on ? ", " : ""}${settings.closes_on ? `closes ${formatDay(settings.closes_on)}` : ""}` : ""}</p></div>
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}>Edit settings</Button>
        </section>
      )}

      {settings.enabled && !editing && (
        <>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by status">
            {FILTERS.map((x) => <button key={x.id} aria-pressed={filter === x.id} onClick={() => setFilter(x.id)} className={`rounded-full px-4 py-2 text-sm font-semibold transition ${filter === x.id ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)] hover:text-ink"}`}>{x.label} <span className="font-normal opacity-70">({counts(x.id)})</span></button>)}
          </div>
          {rows === null ? <Skeleton className="h-32" /> : shown.length === 0 ? (
            <EmptyState title={filter === "pending" ? `No ${term}s waiting` : `No ${term}s here`} body={rows.length === 0 ? `When a college registers a ${term} from your fest page, it shows up here for you to look after.` : "Try another filter."} />
          ) : <ul className="space-y-3">{shown.map((c) => <Row key={c.id} slug={slug} c={c} settings={settings} onChanged={load} />)}</ul>}
        </>
      )}
    </div>
  );
}
