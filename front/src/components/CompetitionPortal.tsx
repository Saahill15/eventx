"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CompetitionMine, MyAuction, MyAuctionName } from "@/lib/types";
import { formatDay, formatTime } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { Notice, Pill, Skeleton } from "@/components/ui/bits";

const signed = (n: number) => (n > 0 ? `+${n}` : String(n));
const LABEL: Record<string, string> = { meet_tasks: "CL meet tasks", auction: "Name auction", event_points: "Event wins", penalties: "Penalties", adjustments: "Adjustments" };

function NameRow({ slug, a, n, balance, reload }: { slug: string; a: MyAuction; n: MyAuctionName; balance: number; reload: () => void }) {
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const base = `/api/fests/${slug}/auctions/${a.id}/names/${n.id}/bid`;
  const act = async (fn: () => Promise<unknown>) => { setBusy(true); setError(""); try { await fn(); setAmount(""); reload(); } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); } setBusy(false); };
  return (
    <li className={`rounded-2xl border p-4 ${n.i_won ? "border-emerald-300 bg-mint/40" : "border-black/10"}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold">{n.name}{n.code && <span className="ml-2 text-[12px] font-normal text-mute">{n.code}</span>}</p>
        {a.status === "closed" ? <p className="text-sm">{n.i_won ? <strong className="text-emerald-800">You won this name</strong> : n.winner_label ? <span className="text-mute">Won by {n.winner_label}</span> : <span className="text-mute">Not sold</span>}</p>
          : n.my_bid !== null ? <Pill tone="green">Your bid: {n.my_bid}</Pill> : <span className="text-[13px] text-mute">No bid from you</span>}
      </div>
      {a.status === "open" && (
        <>
          {n.top_bid !== null && <p className="mt-1 text-[13px] text-mute">Top bid so far: {n.top_bid}</p>}
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <input aria-label={`Your bid for ${n.name}`} className="field !h-10 !w-32" type="number" min={Math.max(a.min_bid, (n.my_bid ?? 0) + 1)} max={balance} placeholder={n.my_bid !== null ? `More than ${n.my_bid}` : `At least ${a.min_bid}`} value={amount} onChange={(e) => setAmount(e.target.value)} />
            <Button size="sm" disabled={busy || !amount} onClick={() => act(() => api(base, { method: "PUT", body: { amount: Number(amount) } }))}>{n.my_bid !== null ? "Raise bid" : "Place bid"}</Button>
            {n.my_bid !== null && <button disabled={busy} onClick={() => act(() => api(base, { method: "DELETE" }))} className="text-[13px] font-semibold text-red-600 underline underline-offset-4">Withdraw</button>}
          </div>
          {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
        </>
      )}
    </li>
  );
}

/**
 * A contingent's points at a glance, and everything that moves them: CL meet tasks, the name auction, event wins and penalties.
 * It shows only this contingent's own figures. Other contingents' bids and points are never part of it.
 */
export function CompetitionPortal({ slug, term }: { slug: string; term: string }) {
  const [d, setD] = useState<CompetitionMine | null | undefined>(undefined);
  const [showLedger, setShowLedger] = useState(false);
  const load = useCallback(() => { api<CompetitionMine | null>(`/api/fests/${slug}/competition/mine`).then(setD).catch(() => setD(null)); }, [slug]);
  useEffect(() => { load(); }, [load]);
  if (d === undefined) return <Skeleton className="h-40" />;
  if (!d) return null;
  const parts = (Object.keys(LABEL) as (keyof typeof d.breakdown)[]).filter((k) => d.breakdown[k] !== 0);
  const open = d.auctions.filter((a) => a.status === "open");
  const closed = d.auctions.filter((a) => a.status === "closed");
  const upcoming = d.meets.filter((m) => new Date(m.starts_at) >= new Date(new Date().setHours(0, 0, 0, 0)));
  const past = d.meets.filter((m) => !upcoming.includes(m));

  return (
    <div className="space-y-6">
      <section className="card p-6 sm:p-8" aria-label="Your points">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div><p className="text-sm text-mute">Your points</p><p className="font-display text-5xl font-semibold leading-none tracking-tight">{d.balance}</p>
            {d.rank !== null && <p className="mt-2 text-sm font-semibold">Ranked {d.rank}</p>}</div>
          <p className="max-w-sm text-sm text-mute">You started with {d.starting_points}. {parts.length > 0 ? parts.map((k) => `${LABEL[k]} ${signed(d.breakdown[k])}`).join(" · ") : "Nothing has moved them yet."}</p>
        </div>
        {d.disqualified && <div className="mt-4"><Notice tone="warn">Your {term} has been disqualified from the competition, so it is left out of the rankings and awards.</Notice></div>}
        <button onClick={() => setShowLedger(!showLedger)} className="mt-4 text-sm font-semibold underline underline-offset-4">{showLedger ? "Hide" : "See"} every change to your points</button>
        {showLedger && (
          <ul className="mt-3 divide-y divide-black/5 rounded-2xl bg-wash px-4 text-sm">
            {d.ledger.length === 0 ? <li className="py-3 text-mute">Nothing yet.</li> : d.ledger.map((e) => <li key={e.id} className="flex justify-between gap-3 py-2.5"><span className="min-w-0">{e.reason}</span><span className={`shrink-0 font-semibold ${e.points < 0 ? "text-red-600" : "text-emerald-700"}`}>{signed(e.points)}</span></li>)}
          </ul>
        )}
      </section>

      {open.map((a) => (
        <section key={a.id} className="card space-y-3 p-6 sm:p-8" aria-label={a.title}>
          <div><h3 className="font-display text-xl font-bold tracking-tight">{a.title} <Pill tone="green">Open for bids</Pill></h3>
            <p className="mt-1 text-sm text-mute">Bid points for the name you want. The highest bid on a name wins it, and you can win only one. {a.show_highest_bid ? "You can see the top bid." : "Bids are sealed: you see only your own."} Only the winning bid is taken off, so everyone else keeps their points. You have {d.balance}.</p></div>
          <ul className="space-y-3">{a.names.map((n) => <NameRow key={n.id} slug={slug} a={a} n={n} balance={d.balance} reload={load} />)}</ul>
        </section>
      ))}
      {closed.map((a) => (
        <section key={a.id} className="card space-y-3 p-6 sm:p-8" aria-label={a.title}>
          <h3 className="font-display text-xl font-bold tracking-tight">{a.title} <Pill tone="neutral">Closed</Pill></h3>
          <ul className="space-y-3">{a.names.map((n) => <NameRow key={n.id} slug={slug} a={a} n={n} balance={d.balance} reload={load} />)}</ul>
        </section>
      ))}

      {d.meets.length > 0 && (
        <section className="card space-y-4 p-6 sm:p-8" aria-label="CL meets">
          <h3 className="font-display text-xl font-bold tracking-tight">CL meets</h3>
          {[...upcoming, ...past].map((m) => (
            <div key={m.id} className="rounded-2xl bg-wash p-4">
              <p className="font-semibold">{m.title}{past.includes(m) && m.attended && <span className="ml-2"><Pill tone="green">You were there</Pill></span>}</p>
              <p className="text-sm text-mute">{formatDay(m.starts_at.slice(0, 10))}, {formatTime(m.starts_at.slice(11, 16))}{m.location ? ` · ${m.location}` : ""}</p>
              {m.notes && <p className="mt-1 text-sm">{m.notes}</p>}
              {m.tasks.length > 0 && <ul className="mt-2 space-y-1 text-sm">{m.tasks.map((t) => <li key={t.id} className="flex justify-between gap-3"><span>{t.title}</span>{t.results.length > 0 && <span className={`font-semibold ${t.results[0].points < 0 ? "text-red-600" : "text-emerald-700"}`}>{signed(t.results[0].points)}</span>}</li>)}</ul>}
            </div>
          ))}
        </section>
      )}

      {d.events.length > 0 && (
        <section className="card space-y-2 p-6 sm:p-8" aria-label="Event results">
          <h3 className="font-display text-xl font-bold tracking-tight">Where you placed</h3>
          <ul className="divide-y divide-black/5 text-sm">{d.events.map((e) => <li key={`${e.contingent_label}-${e.place}`} className="flex justify-between gap-3 py-2.5"><span>{e.contingent_label} · place {e.place}</span><span className={`font-semibold ${e.disqualified ? "text-red-600" : "text-emerald-700"}`}>{e.disqualified ? "Disqualified" : signed(e.points)}</span></li>)}</ul>
        </section>
      )}

      {d.penalties.length > 0 && (
        <section className="card space-y-2 p-6 sm:p-8" aria-label="Penalties">
          <h3 className="font-display text-xl font-bold tracking-tight">Penalties</h3>
          <ul className="divide-y divide-black/5 text-sm">{d.penalties.map((p) => <li key={p.id} className="py-2.5"><p className="font-medium">{p.reason}</p><p className="text-[13px] text-mute">{[p.points ? `−${p.points} points` : null, p.disqualified ? (p.event_title ? `disqualified from ${p.event_title}` : "disqualified from the competition") : null].filter(Boolean).join(" · ")}. If you think it is a mistake, talk to the committee.</p></li>)}</ul>
        </section>
      )}
    </div>
  );
}
