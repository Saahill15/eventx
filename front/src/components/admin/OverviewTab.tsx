"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { FestEvent, FestReview, VerificationReview } from "@/lib/types";
import { formatDay } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/bits";
import { greeting, PageHeader } from "@/components/shell/WorkspaceShell";
import { ListCard, StatStrip, useCounts, when } from "./shared";

interface AuthEvent { id: number; at: string; portal: string; email: string | null; reason: string }
const REASON: Record<string, string> = { bad_credentials: "Wrong password", not_admin: "Not an admin", locked: "Blocked after too many tries", disabled: "Suspended account", admin_on_public_page: "Admin used the public page" };

const Row = ({ href, title, sub, right }: { href: string; title: string; sub?: string; right?: string }) => (
  <Link href={href} className="flex items-center justify-between gap-3 border-b border-[var(--ws-border)] px-5 py-3 last:border-b-0 hover:bg-black/[0.015]">
    <div className="min-w-0"><p className="truncate text-[14px] font-medium">{title}</p>{sub && <p className="truncate text-[13px] text-mute">{sub}</p>}</div>
    {right && <span className="shrink-0 text-[13px] text-mute">{right}</span>}
  </Link>
);
const Empty = ({ text }: { text: string }) => <p className="px-5 py-8 text-center text-[14px] text-mute">{text}</p>;

export function OverviewTab() {
  const { user } = useAuth();
  const o = useCounts();
  const [fests, setFests] = useState<FestReview[] | null>(null);
  const [proofs, setProofs] = useState<VerificationReview[] | null>(null);
  const [events, setEvents] = useState<FestEvent[] | null>(null);
  const [failed, setFailed] = useState<AuthEvent[] | null>(null);

  // Only ask for a list when the numbers say there is something in it
  useEffect(() => {
    if (!o) return;
    const empty = <T,>() => Promise.resolve([] as T[]);
    Promise.all([
      o.fests_in_review ? api<FestReview[]>("/api/admin/fests?review_status=in_review") : empty<FestReview>(),
      o.verifications_pending ? api<VerificationReview[]>("/api/admin/student-verifications?status=pending") : empty<VerificationReview>(),
      o.city_events_pending ? api<FestEvent[]>("/api/admin/events/pending") : empty<FestEvent>(),
      api<AuthEvent[]>("/api/admin/security-log?limit=5&failed_only=true"),
    ]).then(([f, p, e, a]) => { setFests(f); setProofs(p); setEvents(e); setFailed(a); }).catch(() => { setFests([]); setProofs([]); setEvents([]); setFailed([]); });
  }, [o]);

  if (!o) return <div className="space-y-4"><Skeleton className="h-12 w-72" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>;

  const waiting = o.fests_in_review + o.verifications_pending + o.city_events_pending;
  const loading = fests === null;

  return (
    <div className="space-y-6">
      <PageHeader
        title={greeting(user?.first_name)}
        sub={waiting ? `${waiting} thing${waiting === 1 ? " is" : "s are"} waiting for you.` : "Nothing is waiting for you."}
        actions={<><Button href="/admin/people" variant="outline" size="sm">People</Button><Button href="/admin/fests" size="sm">Review fests{o.fests_in_review ? ` (${o.fests_in_review})` : ""}</Button></>}
      />

      <StatStrip items={[
        { label: "Fests to review", value: o.fests_in_review, hint: "Submitted by organisers", alert: true, href: "/admin/fests" },
        { label: "Student proofs", value: o.verifications_pending, hint: "ID photos waiting", alert: true, href: "/admin/verifications" },
        { label: "City events", value: o.city_events_pending, hint: "Waiting for approval", alert: true, href: "/admin/city" },
        { label: "Sent back for changes", value: o.fests_changes_requested, hint: "With the organiser", href: "/admin/fests" },
      ]} />
      <StatStrip items={[
        { label: "Members", value: o.members, hint: `${o.verified_students} verified students`, href: "/admin/people" },
        { label: "Organisers", value: o.organizers, hint: o.suspended ? `${o.suspended} account${o.suspended === 1 ? "" : "s"} suspended` : "None suspended", href: "/admin/people" },
        { label: "Partner colleges", value: o.partner_colleges, hint: `${o.prospect_colleges} prospect${o.prospect_colleges === 1 ? "" : "s"}`, href: "/admin/colleges" },
        { label: "Live fests", value: o.fests_live, hint: `${o.events_total} events · ${o.fest_passes} passes` },
      ]} />

      <div className="grid gap-6 xl:grid-cols-2">
        <ListCard title="Fests waiting for review" count={o.fests_in_review} href="/admin/fests" linkLabel="Open list">
          {loading ? <Skeleton className="m-5 h-16" /> : fests.length === 0 ? <Empty text="No fests are waiting." /> : fests.slice(0, 5).map((r) => (
            <Row key={r.fest.id} href="/admin/fests" title={r.fest.name} sub={`${r.college?.name ?? "No college"} · ${r.events.length} event${r.events.length === 1 ? "" : "s"}${r.missing.length ? ` · ${r.missing.length} missing` : ""}`} right={r.fest.submitted_at ? when(r.fest.submitted_at) : undefined} />
          ))}
        </ListCard>
        <ListCard title="Student proofs" count={o.verifications_pending} href="/admin/verifications" linkLabel="Open list">
          {loading ? <Skeleton className="m-5 h-16" /> : proofs!.length === 0 ? <Empty text="No ID photos are waiting." /> : proofs!.slice(0, 5).map((v) => (
            <Row key={v.id} href="/admin/verifications" title={v.user_name ?? "Unknown"} sub={`${v.college_name ?? "No college"} · ${v.document_type ?? "Proof"}`} right={when(v.created_at)} />
          ))}
        </ListCard>
        <ListCard title="City events" count={o.city_events_pending} href="/admin/city" linkLabel="Open list">
          {loading ? <Skeleton className="m-5 h-16" /> : events!.length === 0 ? <Empty text="No city events are waiting." /> : events!.slice(0, 5).map((e) => (
            <Row key={e.id} href="/admin/city" title={e.title} sub={e.location ?? undefined} right={formatDay(e.date)} />
          ))}
        </ListCard>
        <ListCard title="Failed sign-ins" href="/admin/security" linkLabel="Sign-in log">
          {loading ? <Skeleton className="m-5 h-16" /> : failed!.length === 0 ? <Empty text="No failed sign-in attempts." /> : failed!.map((a) => (
            <Row key={a.id} href="/admin/security" title={a.email || "Unknown email"} sub={`${a.portal === "admin" ? "Admin page" : "Public page"} · ${REASON[a.reason] ?? a.reason}`} right={when(a.at)} />
          ))}
        </ListCard>
      </div>
    </div>
  );
}
