"use client";

import { useCallback, useEffect, useState } from "react";
import { api, downloadFile } from "@/lib/api";
import type { BudgetLine, FinanceCategory, FinanceSettings, FinanceSummary, IncomeItem, Org, Sponsor } from "@/lib/types";
import { formatDay, inr } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";
import { useRun } from "./FinanceSpend";

export type Section = "overview" | "spending" | "budget" | "income" | "settings";

function Bar({ value, pending = 0, max, over }: { value: number; pending?: number; max: number; over?: boolean }) {
  const pct = (n: number) => (max > 0 ? Math.min((n / max) * 100, 100) : n > 0 ? 100 : 0);
  return (
    <div className="h-2 overflow-hidden rounded-full bg-black/[0.07]" role="progressbar" aria-valuenow={Math.round(pct(value))} aria-valuemin={0} aria-valuemax={100}>
      <div className="flex h-full"><div className={`h-full ${over ? "bg-red-500" : "bg-[var(--ws-accent)]"}`} style={{ width: `${pct(value)}%` }} />{pending > 0 && <div className="h-full bg-amber-300" style={{ width: `${Math.min(pct(pending), 100 - pct(value))}%` }} />}</div>
    </div>
  );
}

function Tile({ label, value, hint, tone, onClick }: { label: string; value: string; hint?: string; tone?: "bad" | "warn"; onClick?: () => void }) {
  const body = <><p className="text-[13px] text-mute">{label}</p><p className={`mt-1 text-[24px] font-semibold leading-none tracking-tight ${tone === "bad" ? "text-red-600" : ""}`}>{value}</p>{hint && <p className="mt-1.5 text-[13px] text-mute">{hint}</p>}</>;
  return onClick ? <button onClick={onClick} className="card p-4 text-left transition hover:bg-black/[0.015]">{body}</button> : <div className="card p-4">{body}</div>;
}

// ─── overview ────────────────────────────────────────────────────────────────

/** Where the fest stands: cash, what is committed against the budget, what is still to come, and who is owed. */
export function OverviewPanel({ slug, summary, go }: { slug: string; summary: FinanceSummary | null; go: (s: Section) => void }) {
  if (!summary) return <Skeleton className="h-48" />;
  const s = summary;
  const expense = s.by_category.filter((c) => c.kind === "expense" && (c.planned > 0 || c.committed > 0));
  const income = s.by_category.filter((c) => c.kind === "income" && (c.planned > 0 || c.committed > 0));
  const still = Math.max(s.expected_income - s.cash_in, 0);
  return (
    <div className="max-w-5xl space-y-6">
      {(s.over_budget_lines > 0 || s.unbudgeted > 0 || s.projected_net < 0) && (
        <div className="space-y-2">
          {s.projected_net < 0 && <Notice tone="warn">On what is expected and what is planned, the fest ends {inr(-s.projected_net)} short. Look at the budget or at income still to come.</Notice>}
          {s.over_budget_lines > 0 && <Notice tone="warn">{s.over_budget_lines} budget line{s.over_budget_lines === 1 ? " is" : "s are"} over budget. <button onClick={() => go("budget")} className="font-semibold underline underline-offset-4">See the budget</button></Notice>}
          {s.unbudgeted > 0 && <Notice tone="info">{inr(s.unbudgeted)} has been approved that is not under any budget line.</Notice>}
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Tile label="Cash so far" value={inr(s.cash_position)} hint={`${inr(s.cash_in)} received, ${inr(s.cash_out)} paid out`} tone={s.cash_position < 0 ? "bad" : undefined} />
        <Tile label="Still to come in" value={inr(still)} hint={`${inr(s.expected_income)} expected in all`} onClick={() => go("income")} />
        <Tile label="Budget" value={inr(s.budget_planned)} hint={`${inr(s.committed)} approved or paid`} onClick={() => go("budget")} />
        <Tile label="Waiting for a decision" value={String(s.pending_requests)} hint={s.pending_requests ? `${inr(s.pending)} asked for` : "Nothing waiting"} onClick={() => go("spending")} />
        <Tile label="Approved, not yet paid" value={inr(s.approved)} hint={s.owed_to_members.length ? `${inr(s.owed_to_members.reduce((n, o) => n + o.amount, 0))} owed to members` : undefined} onClick={() => go("spending")} />
        <Tile label="If everything goes to plan" value={inr(s.projected_net)} hint="Expected income less the budget" tone={s.projected_net < 0 ? "bad" : undefined} />
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-2">
        <section className="card overflow-hidden" aria-label="Spending by category">
          <div className="flex h-12 items-center border-b border-[var(--ws-border)] px-5"><h2 className="text-[14px] font-semibold">Spending against the budget</h2></div>
          {expense.length === 0 ? <p className="px-5 py-6 text-sm text-mute">No budget yet. Add budget lines to see how spending compares.</p> : (
            <ul className="divide-y divide-[var(--ws-border)]">{expense.map((c) => (
              <li key={c.category_id} className="px-5 py-3"><div className="mb-1.5 flex justify-between gap-3 text-sm"><span className="font-medium">{c.name}</span><span className={c.committed > c.planned && c.planned > 0 ? "font-semibold text-red-600" : "text-mute"}>{inr(c.committed)} of {inr(c.planned)}</span></div><Bar value={c.committed} max={c.planned} over={c.committed > c.planned} /></li>
            ))}</ul>
          )}
        </section>
        <section className="card overflow-hidden" aria-label="Income by category">
          <div className="flex h-12 items-center border-b border-[var(--ws-border)] px-5"><h2 className="text-[14px] font-semibold">Money coming in</h2></div>
          {income.length === 0 && s.registration_income === 0 && s.college_fees_due === 0 ? <p className="px-5 py-6 text-sm text-mute">Nothing expected yet. Add sponsors, grants and other income.</p> : (
            <ul className="divide-y divide-[var(--ws-border)]">
              {income.map((c) => <li key={c.category_id} className="px-5 py-3"><div className="mb-1.5 flex justify-between gap-3 text-sm"><span className="font-medium">{c.name}</span><span className="text-mute">{inr(c.committed)} of {inr(c.planned)}</span></div><Bar value={c.committed} max={c.planned} /></li>)}
              {s.registration_income > 0 && <li className="flex justify-between px-5 py-3 text-sm"><span className="font-medium">Paid events (through HiveOut)</span><span className="text-mute">{inr(s.registration_income)}</span></li>}
              {s.college_fees_due > 0 && <li className="px-5 py-3"><div className="mb-1.5 flex justify-between gap-3 text-sm"><span className="font-medium">Visiting college fees</span><span className="text-mute">{inr(s.college_fees_received)} of {inr(s.college_fees_due)}</span></div><Bar value={s.college_fees_received} max={s.college_fees_due} /></li>}
            </ul>
          )}
        </section>
      </div>

      {s.by_team.length > 0 && (
        <section className="card overflow-hidden" aria-label="By team">
          <div className="flex h-12 items-center border-b border-[var(--ws-border)] px-5"><h2 className="text-[14px] font-semibold">By team</h2></div>
          <ul className="divide-y divide-[var(--ws-border)]">{s.by_team.map((t) => <li key={t.team_id ?? "none"} className="px-5 py-3"><div className="mb-1.5 flex justify-between gap-3 text-sm"><span className="font-medium">{t.name}</span><span className={t.committed > t.planned ? "font-semibold text-red-600" : "text-mute"}>{inr(t.committed)} of {inr(t.planned)}</span></div><Bar value={t.committed} max={t.planned} over={t.committed > t.planned} /></li>)}</ul>
        </section>
      )}

      {s.owed_to_members.length > 0 && (
        <section className="card overflow-hidden" aria-label="Owed to members">
          <div className="flex h-12 items-center justify-between border-b border-[var(--ws-border)] px-5"><h2 className="text-[14px] font-semibold">Members to pay back</h2><button onClick={() => go("spending")} className="text-[13px] text-mute hover:text-ink">Open requests</button></div>
          <ul className="divide-y divide-[var(--ws-border)]">{s.owed_to_members.map((o) => <li key={o.member_id} className="flex justify-between gap-3 px-5 py-3 text-sm"><span className="font-medium">{o.name}</span><span>{inr(o.amount)} <span className="text-mute">for {o.expenses} request{o.expenses === 1 ? "" : "s"}</span></span></li>)}</ul>
        </section>
      )}

      <div><Button size="sm" variant="outline" onClick={() => downloadFile(`/api/fests/${slug}/finance/export`, `${slug}-finance.csv`)}>Download everything as a spreadsheet</Button></div>
    </div>
  );
}

// ─── budget ──────────────────────────────────────────────────────────────────

function LineForm({ slug, line, cats, teams, onDone }: { slug: string; line?: BudgetLine; cats: FinanceCategory[]; teams: Org["teams"]; onDone: () => void }) {
  const [f, setF] = useState({ title: line?.title ?? "", category: line ? String(line.category_id) : "", planned: line ? String(line.planned) : "", team: line?.committee_team_id ? String(line.committee_team_id) : "", notes: line?.notes ?? "" });
  const { run, error, busy } = useRun(onDone);
  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const body = { title: f.title, category_id: Number(f.category), planned: Number(f.planned) || 0, committee_team_id: f.team ? Number(f.team) : null, notes: f.notes || null };
    run(() => api(line ? `/api/fests/${slug}/finance/budget/${line.id}` : `/api/fests/${slug}/finance/budget`, { method: line ? "PATCH" : "POST", body }));
  };
  return (
    <form onSubmit={save} className="space-y-3 rounded-2xl bg-wash p-4">
      <ErrorNote>{error}</ErrorNote>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="What is it for?"><input className="field" required maxLength={200} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="e.g. Hall hire" /></Field>
        <Field label="Category"><select className="field" required value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}><option value="">Choose</option>{cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
        <Field label="Planned amount (₹)"><input className="field" type="number" required min={0} step="0.01" value={f.planned} onChange={(e) => setF({ ...f, planned: e.target.value })} /></Field>
        <Field label="Which team looks after it?" hint="Optional"><select className="field" value={f.team} onChange={(e) => setF({ ...f, team: e.target.value })}><option value="">No team</option>{teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
      </div>
      <Field label="Notes"><input className="field" maxLength={500} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy || !f.title.trim() || !f.category}>{line ? "Save" : "Add to the budget"}</Button><Button size="sm" type="button" variant="ghost" onClick={onDone}>Cancel</Button></div>
    </form>
  );
}

/** The plan: what each thing is expected to cost, and how much of it has been asked for, approved and paid. */
export function BudgetPanel({ slug, cats, reloadAll, go }: { slug: string; cats: FinanceCategory[]; reloadAll: () => void; go: (s: Section) => void }) {
  const [lines, setLines] = useState<BudgetLine[] | null>(null);
  const [teams, setTeams] = useState<Org["teams"]>([]);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const load = useCallback(() => { api<BudgetLine[]>(`/api/fests/${slug}/finance/budget`).then(setLines).catch(() => setLines([])); reloadAll(); }, [slug, reloadAll]);
  useEffect(() => { load(); api<Org>(`/api/fests/${slug}/org`).then((o) => setTeams(o.teams)).catch(() => {}); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const { run, error, busy } = useRun(load);
  const expenseCats = cats.filter((c) => c.kind === "expense");
  if (!lines) return <Skeleton className="h-40" />;
  if (expenseCats.length === 0) return <EmptyState title="Set up your categories first" body="Categories are the kinds of spending your fest has (venue, prizes, food...). Add the usual set and change it to suit, or make your own under Settings." action={<Button onClick={() => go("settings")}>Open settings</Button>} />;
  const total = lines.reduce((n, l) => n + l.planned, 0);
  const grouped = expenseCats.map((c) => ({ c, items: lines.filter((l) => l.category_id === c.id) })).filter((g) => g.items.length > 0);
  return (
    <div className="max-w-4xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-mute">{lines.length} line{lines.length === 1 ? "" : "s"} · {inr(total)} planned. The bar shows what is approved or paid; the amber part is still waiting for a decision.</p><Button size="sm" onClick={() => setEditing(editing === "new" ? null : "new")}>{editing === "new" ? "Close" : "Add a budget line"}</Button></div>
      <ErrorNote>{error}</ErrorNote>
      {editing === "new" && <LineForm slug={slug} cats={expenseCats} teams={teams} onDone={() => { setEditing(null); load(); }} />}
      {lines.length === 0 && editing !== "new" ? <EmptyState title="No budget yet" body="Add a line for each thing you expect to spend on, with how much. People then ask to spend against a line, and you see how far each one has gone." /> : grouped.map(({ c, items }) => (
        <section key={c.id} className="space-y-2" aria-label={c.name}>
          <p className="flex justify-between text-xs font-bold uppercase tracking-[0.14em] text-mute"><span>{c.name}</span><span>{inr(items.reduce((n, l) => n + l.planned, 0))}</span></p>
          {items.map((l) => (
            <div key={l.id} className="card p-4">
              {editing === l.id ? <LineForm slug={slug} line={l} cats={expenseCats} teams={teams} onDone={() => { setEditing(null); load(); }} /> : (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0"><p className="flex flex-wrap items-center gap-2 font-semibold">{l.title}{l.over_budget && <Pill tone="red">Over budget</Pill>}</p><p className="text-[13px] text-mute">{l.team_name ? `${l.team_name} · ` : ""}{l.notes ?? ""}</p></div>
                    <div className="text-right"><p className="font-semibold">{inr(l.committed)} <span className="font-normal text-mute">of {inr(l.planned)}</span></p><p className={`text-[13px] ${l.remaining < 0 ? "font-semibold text-red-600" : "text-mute"}`}>{l.remaining < 0 ? `${inr(-l.remaining)} over` : `${inr(l.remaining)} left`}{l.pending > 0 ? ` · ${inr(l.pending)} waiting` : ""}</p></div>
                  </div>
                  <div className="mt-3"><Bar value={l.committed} pending={l.pending} max={l.planned} over={l.over_budget} /></div>
                  <div className="mt-3 flex gap-4 text-[13px] font-semibold"><button onClick={() => setEditing(l.id)} className="underline underline-offset-4">Edit</button><button disabled={busy} onClick={() => window.confirm(`Delete “${l.title}” from the budget?`) && run(() => api(`/api/fests/${slug}/finance/budget/${l.id}`, { method: "DELETE" }))} className="text-red-600 hover:underline">Delete</button></div>
                </>
              )}
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

// ─── income ──────────────────────────────────────────────────────────────────

const INCOME_TONE = { pledged: "neutral", partial: "amber", received: "green", overdue: "red" } as const;
const INCOME_TEXT = { pledged: "Expected", partial: "Part received", received: "Received", overdue: "Overdue" } as const;

function IncomeForm({ slug, cats, sponsors, item, onDone }: { slug: string; cats: FinanceCategory[]; sponsors: Sponsor[]; item?: IncomeItem; onDone: () => void }) {
  const [f, setF] = useState({ title: item?.title ?? "", category: item ? String(item.category_id) : "", source: item?.source ?? "", sponsor: item?.sponsor_id ? String(item.sponsor_id) : "", expected: item ? String(item.expected) : "", due: item?.due_on ?? "" });
  const { run, error, busy } = useRun(onDone);
  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const body = { title: f.title, category_id: Number(f.category), source: f.source || null, sponsor_id: f.sponsor ? Number(f.sponsor) : null, expected: Number(f.expected) || 0, due_on: f.due || null };
    run(() => api(item ? `/api/fests/${slug}/finance/income/${item.id}` : `/api/fests/${slug}/finance/income`, { method: item ? "PATCH" : "POST", body }));
  };
  return (
    <form onSubmit={save} className="space-y-3 rounded-2xl bg-wash p-4">
      <ErrorNote>{error}</ErrorNote>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="What is it?"><input className="field" required maxLength={200} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="e.g. Acme Bank title sponsorship" /></Field>
        <Field label="Category"><select className="field" required value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}><option value="">Choose</option>{cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
        <Field label="Amount expected (₹)"><input className="field" type="number" required min={0} step="0.01" value={f.expected} onChange={(e) => setF({ ...f, expected: e.target.value })} /></Field>
        <Field label="Due on" hint="Optional"><input className="field" type="date" value={f.due} onChange={(e) => setF({ ...f, due: e.target.value })} /></Field>
        <Field label="From whom?" hint="Optional"><input className="field" maxLength={120} value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })} /></Field>
        {sponsors.length > 0 && <Field label="Link to a listed sponsor" hint="Optional"><select className="field" value={f.sponsor} onChange={(e) => setF({ ...f, sponsor: e.target.value })}><option value="">Not a sponsor</option>{sponsors.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>}
      </div>
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy || !f.title.trim() || !f.category}>{item ? "Save" : "Add"}</Button><Button size="sm" type="button" variant="ghost" onClick={onDone}>Cancel</Button></div>
    </form>
  );
}

function IncomeCard({ slug, i, cats, sponsors, reload }: { slug: string; i: IncomeItem; cats: FinanceCategory[]; sponsors: Sponsor[]; reload: () => void }) {
  const [editing, setEditing] = useState(false);
  const [pay, setPay] = useState({ amount: "", method: "" });
  const { run, error, busy } = useRun(reload);
  if (editing) return <li className="card p-4"><IncomeForm slug={slug} cats={cats} sponsors={sponsors} item={i} onDone={() => { setEditing(false); reload(); }} /></li>;
  const base = `/api/fests/${slug}/finance/income`;
  return (
    <li className="card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0"><p className="flex flex-wrap items-center gap-2 font-semibold">{i.title}<Pill tone={INCOME_TONE[i.status]}>{INCOME_TEXT[i.status]}</Pill></p><p className="text-[13px] text-mute">{i.category_name}{i.source ? ` · ${i.source}` : ""}{i.sponsor_name && i.sponsor_name !== i.source ? ` · sponsor ${i.sponsor_name}` : ""}{i.due_on ? ` · due ${formatDay(i.due_on)}` : ""}</p></div>
        <div className="text-right"><p className="font-semibold">{inr(i.received)} <span className="font-normal text-mute">of {inr(i.expected)}</span></p>{i.outstanding > 0 && <p className="text-[13px] text-mute">{inr(i.outstanding)} to come</p>}</div>
      </div>
      <div className="mt-3"><Bar value={i.received} max={i.expected} /></div>
      {i.payments.length > 0 && <ul className="mt-3 space-y-1 text-sm">{i.payments.map((p) => <li key={p.id} className="flex justify-between gap-3"><span>{formatDay(p.received_on)}{p.method ? ` · ${p.method}` : ""}{p.note ? ` · ${p.note}` : ""}</span><span>{inr(p.amount)}<button disabled={busy} onClick={() => window.confirm("Delete this payment?") && run(() => api(`${base}/payments/${p.id}`, { method: "DELETE" }))} className="ml-3 text-[12px] font-semibold text-red-600 hover:underline">Delete</button></span></li>)}</ul>}
      <ErrorNote>{error}</ErrorNote>
      <form onSubmit={(e) => { e.preventDefault(); run(() => api(`${base}/${i.id}/payments`, { method: "POST", body: { amount: Number(pay.amount), method: pay.method || null } })).then((ok) => ok && setPay({ amount: "", method: "" })); }} className="mt-3 flex flex-wrap items-end gap-2">
        <div className="w-36"><Field label="Money received (₹)"><input className="field !h-10" type="number" min={0.01} step="0.01" value={pay.amount} onChange={(e) => setPay({ ...pay, amount: e.target.value })} /></Field></div>
        <div className="w-40"><Field label="How"><input className="field !h-10" maxLength={40} value={pay.method} onChange={(e) => setPay({ ...pay, method: e.target.value })} placeholder="Cheque, UPI…" /></Field></div>
        <Button size="sm" variant="outline" type="submit" disabled={busy || !pay.amount}>Record</Button>
        <span className="ml-auto flex gap-4 text-[13px] font-semibold"><button type="button" onClick={() => setEditing(true)} className="underline underline-offset-4">Edit</button><button type="button" disabled={busy} onClick={() => window.confirm(`Delete “${i.title}”?`) && run(() => api(`${base}/${i.id}`, { method: "DELETE" }))} className="text-red-600 hover:underline">Delete</button></span>
      </form>
    </li>
  );
}

/** Money the fest expects (sponsors, grants, stalls) and what has actually arrived. */
export function IncomePanel({ slug, cats, summary, reloadAll, go }: { slug: string; cats: FinanceCategory[]; summary: FinanceSummary | null; reloadAll: () => void; go: (s: Section) => void }) {
  const [list, setList] = useState<IncomeItem[] | null>(null);
  const [sponsors, setSponsors] = useState<Sponsor[]>([]);
  const [adding, setAdding] = useState(false);
  const load = useCallback(() => { api<IncomeItem[]>(`/api/fests/${slug}/finance/income`).then(setList).catch(() => setList([])); reloadAll(); }, [slug, reloadAll]);
  useEffect(() => { load(); api<Sponsor[]>(`/api/fests/${slug}/sponsors`).then(setSponsors).catch(() => {}); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const incomeCats = cats.filter((c) => c.kind === "income");
  if (!list) return <Skeleton className="h-40" />;
  if (incomeCats.length === 0) return <EmptyState title="Set up your categories first" body="Add the usual income categories (sponsorship, grants, stalls...) under Settings, then list what you expect here." action={<Button onClick={() => go("settings")}>Open settings</Button>} />;
  return (
    <div className="max-w-4xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-mute">Money you expect from sponsors, grants and others. Record each payment as it arrives.</p><Button size="sm" onClick={() => setAdding(!adding)}>{adding ? "Close" : "Add income"}</Button></div>
      {adding && <IncomeForm slug={slug} cats={incomeCats} sponsors={sponsors} onDone={() => { setAdding(false); load(); }} />}
      {list.length === 0 && !adding ? <EmptyState title="No income listed yet" body="Add each sponsor's pledge, the college grant and anything else you expect, then record the money as it comes in." /> : <ul className="space-y-3">{list.map((i) => <IncomeCard key={i.id} slug={slug} i={i} cats={incomeCats} sponsors={sponsors} reload={load} />)}</ul>}
      {summary && (summary.registration_income > 0 || summary.college_fees_due > 0) && (
        <section className="card space-y-2 p-4" aria-label="Collected automatically">
          <p className="text-sm font-semibold">Collected through HiveOut <span className="font-normal text-mute">(counted for you, nothing to record)</span></p>
          {summary.registration_income > 0 && <p className="flex justify-between text-sm"><span>Paid events</span><span>{inr(summary.registration_income)}</span></p>}
          {summary.college_fees_due > 0 && <p className="flex justify-between text-sm"><span>Visiting college fees</span><span>{inr(summary.college_fees_received)} of {inr(summary.college_fees_due)}</span></p>}
        </section>
      )}
    </div>
  );
}

// ─── settings and categories ─────────────────────────────────────────────────

/** The fest's rules for money, and its own categories. */
export function SettingsPanel({ slug, cats, reloadAll }: { slug: string; cats: FinanceCategory[]; reloadAll: () => void }) {
  const [s, setS] = useState<FinanceSettings | null>(null);
  const [auto, setAuto] = useState("");
  const [receipts, setReceipts] = useState<{ on: boolean; over: string }>({ on: true, over: "1000" });
  const [saved, setSaved] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const load = useCallback(() => { api<FinanceSettings>(`/api/fests/${slug}/finance/settings`).then((r) => { setS(r); setAuto(String(r.auto_approve_below)); setReceipts({ on: r.receipt_required_above !== null, over: String(r.receipt_required_above ?? 1000) }); }); }, [slug]);
  useEffect(() => { load(); }, [load]);
  const afterRules = useCallback(() => { setSaved(true); load(); }, [load]);
  const rules = useRun(afterRules);
  const cat = useRun(reloadAll);
  if (!s) return <Skeleton className="h-40" />;
  const save = (e: React.FormEvent) => {
    e.preventDefault(); setSaved(false);
    rules.run(() => api(`/api/fests/${slug}/finance/settings`, { method: "PUT", body: { auto_approve_below: Number(auto) || 0, ...(receipts.on ? { receipt_required_above: Number(receipts.over) || 0 } : { receipts_never_needed: true }) } }));
  };
  return (
    <div className="max-w-3xl space-y-6">
      <form onSubmit={save} className="card space-y-4 p-5" aria-label="Rules for money">
        <div><h2 className="text-[15px] font-semibold">Rules for spending</h2><p className="text-sm text-mute">Every fest runs its money differently. Set what suits yours. You can change these any time.</p></div>
        <ErrorNote>{rules.error}</ErrorNote>
        {saved && <Notice tone="ok">Saved.</Notice>}
        <Field label="Approve small requests on the spot (₹)" hint="A request for less than this needs nobody's approval. Leave at 0 to decide every request yourselves."><input className="field max-w-xs" type="number" min={0} step="0.01" value={auto} onChange={(e) => setAuto(e.target.value)} /></Field>
        <div className="space-y-2">
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={receipts.on} onChange={(e) => setReceipts({ ...receipts, on: e.target.checked })} /><span><strong>Ask for a receipt on bigger requests</strong><span className="block text-mute">Switch off if your committee does not need receipts.</span></span></label>
          {receipts.on && <Field label="Receipt needed for requests above (₹)"><input className="field max-w-xs" type="number" min={0} step="0.01" value={receipts.over} onChange={(e) => setReceipts({ ...receipts, over: e.target.value })} /></Field>}
        </div>
        <Button size="sm" type="submit" disabled={rules.busy}>{rules.busy ? "Saving…" : "Save"}</Button>
      </form>

      <section className="card space-y-4 p-5" aria-label="Categories">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-[15px] font-semibold">Categories</h2><p className="text-sm text-mute">The kinds of money in and out. Name them your own way.</p></div>
          {cats.length < 15 && <Button size="sm" variant="outline" disabled={cat.busy} onClick={() => cat.run(() => api(`/api/fests/${slug}/finance/categories/usual`, { method: "POST" }))}>Add the usual categories</Button>}</div>
        <ErrorNote>{cat.error}</ErrorNote>
        {(["expense", "income"] as const).map((k) => (
          <div key={k}><p className="mb-1.5 text-xs font-bold uppercase tracking-[0.14em] text-mute">{k === "expense" ? "Spending" : "Income"}</p>
            <ul className="divide-y divide-[var(--ws-border)] rounded-xl bg-wash px-3">{cats.filter((c) => c.kind === k).length === 0 ? <li className="py-3 text-sm text-mute">None yet.</li> : cats.filter((c) => c.kind === k).map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-3 py-2.5 text-sm"><span>{c.name}</span>
                <span className="flex gap-3 text-[13px] font-semibold"><button onClick={() => { const n = window.prompt("New name", c.name); if (n && n.trim() && n !== c.name) cat.run(() => api(`/api/fests/${slug}/finance/categories/${c.id}`, { method: "PATCH", body: { name: n.trim() } })); }} className="underline underline-offset-4">Rename</button>
                  <button disabled={cat.busy || c.used} title={c.used ? "Something is filed under it" : ""} onClick={() => window.confirm(`Delete “${c.name}”?`) && cat.run(() => api(`/api/fests/${slug}/finance/categories/${c.id}`, { method: "DELETE" }))} className="text-red-600 hover:underline disabled:opacity-30 disabled:no-underline">Delete</button></span></li>
            ))}</ul></div>
        ))}
        <form onSubmit={(e) => { e.preventDefault(); cat.run(() => api(`/api/fests/${slug}/finance/categories`, { method: "POST", body: { name, kind } })).then((ok) => ok && setName("")); }} className="flex flex-wrap items-end gap-3 border-t border-black/5 pt-4">
          <div className="min-w-[12rem] flex-1"><Field label="Add a category"><input className="field" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Photography" /></Field></div>
          <div className="w-40"><Field label="For"><select className="field" value={kind} onChange={(e) => setKind(e.target.value as "expense" | "income")}><option value="expense">Spending</option><option value="income">Income</option></select></Field></div>
          <Button type="submit" size="sm" disabled={cat.busy || !name.trim()}>Add</Button>
        </form>
      </section>
    </div>
  );
}
