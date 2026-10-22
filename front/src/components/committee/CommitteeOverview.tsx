"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { FestStats, MyFest } from "@/lib/types";
import { formatDay } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/bits";
import { Stat } from "@/components/admin/shared";
import { ReviewPill, useMyFests } from "./CommitteeShell";

type Row = { fest: MyFest; stats: FestStats | null };

export function CommitteeOverview() {
  const { user } = useAuth();
  const { fests } = useMyFests();
  const [rows, setRows] = useState<Row[] | null>(null);
  const canCreate = user?.role === "organizer";

  // Numbers come from each fest the person can manage; volunteers cannot see them, so those fests just show no stats
  useEffect(() => {
    if (!fests) return;
    let cancelled = false;
    Promise.all(fests.map(async (fest) => ({ fest, stats: await api<FestStats>(`/api/fests/${fest.slug}/manage/stats`).catch(() => null) }))).then((r) => { if (!cancelled) setRows(r); });
    return () => { cancelled = true; };
  }, [fests]);

  if (!fests || !rows) return <div className="grid gap-4 sm:grid-cols-3"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>;

  if (fests.length === 0) {
    return (
      <EmptyState
        title={canCreate ? "No fests yet" : "You are not on a fest committee"}
        body={canCreate ? "Create your first fest, fill in its details, add events and send it to HiveOut for review." : "Committee tools appear here once you are added to a fest team."}
        action={canCreate ? <Button href="/dashboard/fests#new">Create a fest</Button> : undefined}
      />
    );
  }

  const stats = rows.flatMap((r) => (r.stats ? [r.stats] : []));
  const sum = (f: (s: FestStats) => number) => stats.reduce((n, s) => n + f(s), 0);
  const pending = sum((s) => s.events.reduce((n, e) => n + e.pending, 0));
  const upcoming = rows.flatMap((r) => (r.stats?.events ?? []).filter((e) => !e.cancelled && new Date(e.date) >= new Date(new Date().setHours(0, 0, 0, 0)) ).map((e) => ({ ...e, fest: r.fest }))).sort((a, b) => a.date.localeCompare(b.date)).slice(0, 6);
  const attention = rows.filter(({ fest, stats: s }) => fest.review_status === "changes_requested" || fest.review_status === "rejected" || (s?.events.some((e) => e.pending > 0) ?? false));
  const count = (st: string) => fests.filter((f) => f.review_status === st).length;

  return (
    <div className="space-y-10">
      <section>
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(15rem,1fr))]">
          <Stat label="Live fests" value={fests.filter((f) => f.status === "live").length} hint={`${fests.length} in total`} />
          <Stat label="With HiveOut for review" value={count("in_review")} hint={`${count("draft")} still drafts`} />
          <Stat label="Entry passes issued" value={sum((s) => s.passes_issued)} hint={`${sum((s) => s.passes_checked_in)} checked in at the gate`} />
          <Stat label="Registrations to approve" value={pending} tone="alert" hint="Across all your fests" />
        </div>
      </section>

      <section>
        <h2 className="mb-4 font-display text-xl font-semibold tracking-tight">Needs your attention</h2>
        {attention.length === 0 ? <p className="card p-6 text-mute">Nothing needs you right now.</p> : (
          <div className="space-y-3">
            {attention.map(({ fest, stats: s }) => {
              const pend = s?.events.reduce((n, e) => n + e.pending, 0) ?? 0;
              return (
                <Link key={fest.id} href={`/dashboard/fests/${fest.slug}`} className="card block p-5 transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)]">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="font-semibold">{fest.name}</p>
                    <div className="flex items-center gap-2"><ReviewPill status={fest.review_status} />{pend > 0 && <span className="rounded-full bg-brand px-2.5 py-1 text-xs font-bold text-on-brand">{pend} to approve</span>}</div>
                  </div>
                  {fest.review_note && (fest.review_status === "changes_requested" || fest.review_status === "rejected") && <p className="mt-2 text-sm text-neutral-700"><span className="font-semibold">HiveOut said:</span> {fest.review_note}</p>}
                </Link>
              );
            })}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-4 font-display text-xl font-semibold tracking-tight">Coming up</h2>
        {upcoming.length === 0 ? <p className="card p-6 text-mute">No upcoming events yet.</p> : (
          <ul className="card divide-y divide-black/5 px-6">
            {upcoming.map((e) => (
              <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 py-3.5">
                <div className="min-w-0"><p className="truncate font-semibold">{e.title}</p><p className="text-xs text-mute">{e.fest.name} · {formatDay(e.date)}</p></div>
                <p className="text-sm text-mute">{e.requires_registration ? `${e.registered}${e.registration_limit ? ` / ${e.registration_limit}` : ""} registered` : "Open entry"}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
