"use client";

import { useRouter } from "next/navigation";
import { Skeleton } from "@/components/ui/bits";
import { Stat, useCounts } from "./shared";

export function OverviewTab() {
  const o = useCounts();
  const router = useRouter();
  const go = (path: string) => router.push(path);

  if (!o) return <div className="grid gap-4 sm:grid-cols-3"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>;

  return (
    <div className="space-y-10">
      <section>
        <h2 className="mb-4 font-display text-xl font-semibold tracking-tight">Needs your attention</h2>
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(15rem,1fr))]">
          <Stat label="Fests to review" value={o.fests_in_review} tone="alert" hint="Submitted by organisers" onClick={() => go("/admin/fests")} />
          <Stat label="Student proofs" value={o.verifications_pending} tone="alert" hint="ID photos waiting" onClick={() => go("/admin/verifications")} />
          <Stat label="City events" value={o.city_events_pending} tone="alert" hint="Waiting for approval" onClick={() => go("/admin/city")} />
          <Stat label="Sent back for changes" value={o.fests_changes_requested} hint="With the organiser" onClick={() => go("/admin/fests")} />
        </div>
      </section>

      <section>
        <h2 className="mb-4 font-display text-xl font-semibold tracking-tight">Platform</h2>
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(15rem,1fr))]">
          <Stat label="Members" value={o.members} hint={`${o.verified_students} verified students`} onClick={() => go("/admin/people")} />
          <Stat label="Organisers" value={o.organizers} onClick={() => go("/admin/people")} />
          <Stat label="Admins" value={o.admins} hint={o.suspended ? `${o.suspended} account${o.suspended === 1 ? "" : "s"} suspended` : undefined} />
          <Stat label="Partner colleges" value={o.partner_colleges} hint={`${o.prospect_colleges} prospects`} onClick={() => go("/admin/colleges")} />
          <Stat label="Live fests" value={o.fests_live} hint={`${o.fests_draft} in draft`} />
          <Stat label="Events" value={o.events_total} />
          <Stat label="Entry passes" value={o.fest_passes} />
          <Stat label="Registrations" value={o.registrations} />
        </div>
      </section>
    </div>
  );
}
