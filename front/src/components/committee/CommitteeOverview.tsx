"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canHostFests } from "@/lib/permissions";
import type { FestStats, MyFest } from "@/lib/types";
import { formatDay } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/bits";
import { ListCard, StatStrip } from "@/components/admin/shared";
import { greeting, PageHeader } from "@/components/shell/WorkspaceShell";
import { ReviewPill, useMyFests } from "./CommitteeShell";
import { IncomingTransfers } from "./IncomingTransfers";

type Row = { fest: MyFest; stats: FestStats | null };

// Where a fest is on its way to going live: one column each
const COLUMNS = [
  { id: "draft", label: "Building", dot: "border-neutral-400", match: (f: MyFest) => f.status !== "live" && (f.review_status === "draft" || f.review_status === "changes_requested" || f.review_status === "rejected") },
  { id: "review", label: "With HiveOut", dot: "border-amber-500", match: (f: MyFest) => f.status !== "live" && f.review_status === "in_review" },
  { id: "approved", label: "Approved", dot: "border-sky-500", match: (f: MyFest) => f.status !== "live" && f.review_status === "approved" },
  { id: "live", label: "Live", dot: "border-emerald-500 bg-emerald-500", match: (f: MyFest) => f.status === "live" },
];

export function CommitteeOverview() {
  const { user } = useAuth();
  const { fests } = useMyFests();
  const [rows, setRows] = useState<Row[] | null>(null);
  const canCreate = canHostFests(user);

  // Numbers come from each fest the person can manage; volunteers cannot see them, so those fests just show no stats
  useEffect(() => {
    if (!fests) return;
    let cancelled = false;
    Promise.all(fests.map(async (fest) => ({ fest, stats: await api<FestStats>(`/api/fests/${fest.slug}/manage/stats`).catch(() => null) }))).then((r) => { if (!cancelled) setRows(r); });
    return () => { cancelled = true; };
  }, [fests]);

  if (!fests || !rows) return <div className="space-y-4"><Skeleton className="h-12 w-72" /><Skeleton className="h-28" /><Skeleton className="h-40" /></div>;

  const header = (sub: string, actions?: React.ReactNode) => <PageHeader title={greeting(user?.first_name)} sub={sub} actions={actions} />;

  if (fests.length === 0) {
    return (
      <div className="space-y-6">
        {header(canCreate ? "Create your first fest to get started." : "You are not on a fest team yet.")}
        <IncomingTransfers />
        <EmptyState
          title={canCreate ? "No fests yet" : "You are not on a fest committee"}
          body={canCreate ? "Create your first fest, fill in its details, add events and send it to HiveOut for review." : "Committee tools appear here once you are added to a fest team."}
          action={canCreate ? <Button href="/dashboard/fests#new">Create a fest</Button> : undefined}
        />
      </div>
    );
  }

  const stats = rows.flatMap((r) => (r.stats ? [r.stats] : []));
  const sum = (f: (s: FestStats) => number) => stats.reduce((n, s) => n + f(s), 0);
  const pending = sum((s) => s.events.reduce((n, e) => n + e.pending, 0));
  const today = new Date(new Date().setHours(0, 0, 0, 0));
  const upcoming = rows.flatMap((r) => (r.stats?.events ?? []).filter((e) => !e.cancelled && new Date(e.date) >= today).map((e) => ({ ...e, fest: r.fest }))).sort((a, b) => a.date.localeCompare(b.date)).slice(0, 6);
  const attention = rows.filter(({ fest, stats: s }) => fest.review_status === "changes_requested" || fest.review_status === "rejected" || (s?.events.some((e) => e.pending > 0) ?? false));
  const count = (st: string) => fests.filter((f) => f.review_status === st).length;
  const live = fests.filter((f) => f.status === "live").length;

  return (
    <div className="space-y-6">
      {header(pending ? `${pending} registration${pending === 1 ? " is" : "s are"} waiting for you.` : attention.length ? "Something needs your attention." : "Nothing is waiting for you.",
        <>{canCreate && <Button href="/dashboard/fests#new" size="sm">New fest</Button>}<Button href="/dashboard/fests" variant="outline" size="sm">All fests</Button></>)}
      <IncomingTransfers />

      <StatStrip items={[
        { label: "Live fests", value: live, hint: `${fests.length} in total`, href: "/dashboard/fests" },
        { label: "With HiveOut", value: count("in_review"), hint: `${count("draft")} still being built`, href: "/dashboard/fests" },
        { label: "Entry passes", value: sum((s) => s.passes_issued), hint: `${sum((s) => s.passes_checked_in)} checked in at the gate` },
        { label: "To approve", value: pending, hint: "Registrations across your fests", alert: true },
      ]} />

      <ListCard title="Your fests" count={fests.length} href="/dashboard/fests" linkLabel="Open list">
        <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-4">
          {COLUMNS.map((col) => {
            const items = fests.filter(col.match);
            return (
              <div key={col.id} className="min-w-0">
                <p className="mb-3 flex items-center gap-2 text-[14px] font-medium"><span className={`h-3 w-3 rounded-full border-2 ${col.dot}`} />{col.label}<span className="font-normal text-mute">{items.length}</span></p>
                {items.length === 0 ? <p className="rounded-lg border border-dashed border-[#d5dcd9] px-3 py-5 text-center text-[13px] text-mute">Nothing here</p> : (
                  <div className="space-y-2">
                    {items.map((f) => (
                      <Link key={f.id} href={`/dashboard/fests/${f.slug}`} className="block rounded-lg border border-[var(--ws-border)] p-3 transition hover:bg-black/[0.02]">
                        <p className="truncate text-[14px] font-semibold">{f.name}</p>
                        <p className="mt-0.5 truncate text-[13px] text-mute">{f.event_count} event{f.event_count === 1 ? "" : "s"}{f.tagline ? ` · ${f.tagline}` : ""}</p>
                        {col.id === "draft" && f.review_status !== "draft" && <div className="mt-2"><ReviewPill status={f.review_status} /></div>}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </ListCard>

      <div className="grid gap-6 xl:grid-cols-2">
        <ListCard title="Needs your attention" count={attention.length}>
          {attention.length === 0 ? <p className="px-5 py-8 text-center text-[14px] text-mute">Nothing needs you right now.</p> : attention.map(({ fest, stats: s }) => {
            const pend = s?.events.reduce((n, e) => n + e.pending, 0) ?? 0;
            return (
              <Link key={fest.id} href={`/dashboard/fests/${fest.slug}`} className="block border-b border-[var(--ws-border)] px-5 py-3 last:border-b-0 hover:bg-black/[0.015]">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[14px] font-medium">{fest.name}</p>
                  <div className="flex items-center gap-2"><ReviewPill status={fest.review_status} />{pend > 0 && <span className="rounded-full bg-tint px-2 py-0.5 text-[12px] font-semibold text-tint-ink">{pend} to approve</span>}</div>
                </div>
                {fest.review_note && (fest.review_status === "changes_requested" || fest.review_status === "rejected") && <p className="mt-1 text-[13px] text-mute"><span className="font-medium text-ink">HiveOut said:</span> {fest.review_note}</p>}
              </Link>
            );
          })}
        </ListCard>
        <ListCard title="Coming up" count={upcoming.length}>
          {upcoming.length === 0 ? <p className="px-5 py-8 text-center text-[14px] text-mute">No upcoming events yet.</p> : upcoming.map((e) => (
            <div key={e.id} className="flex items-center justify-between gap-3 border-b border-[var(--ws-border)] px-5 py-3 last:border-b-0">
              <div className="min-w-0"><p className="truncate text-[14px] font-medium">{e.title}</p><p className="truncate text-[13px] text-mute">{e.fest.name} · {formatDay(e.date)}</p></div>
              <p className="shrink-0 text-[13px] text-mute">{e.requires_registration ? `${e.registered}${e.registration_limit ? ` / ${e.registration_limit}` : ""} registered` : "Open entry"}</p>
            </div>
          ))}
        </ListCard>
      </div>
    </div>
  );
}
