"use client";

import type { Member } from "@/lib/types";
import { Pill } from "@/components/ui/bits";

const ACCESS: Record<string, string> = { owner: "Director", core: "Core team", volunteer: "Volunteer" };

/** The members of the fest as a tree: each person sits under the person they report to. */
export function OrgChart({ members, meId }: { members: Member[]; meId?: number }) {
  const children = new Map<number | null, Member[]>();
  for (const m of members) {
    const key = m.reports_to_id ?? null;
    children.set(key, [...(children.get(key) ?? []), m]);
  }
  const byName = (a: Member, b: Member) => (a.user_name ?? "").localeCompare(b.user_name ?? "");
  const roots = (children.get(null) ?? []).sort(byName);
  const top = roots.filter((m) => m.role === "owner");
  const unplaced = roots.filter((m) => m.role !== "owner");

  const Node = ({ m }: { m: Member }) => {
    const reports = (children.get(m.id) ?? []).sort(byName);
    return (
      <li>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5">
          <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-chip text-xs font-bold">{(m.user_name ?? "?").trim().charAt(0).toUpperCase()}</span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold">{m.user_name}{m.user_id === meId ? " (you)" : ""}</span>
            <span className="block text-xs text-mute">{m.title || ACCESS[m.role]}{m.title ? ` · ${ACCESS[m.role]}` : ""}</span>
          </span>
          {m.team_name && <Pill tone="neutral">{m.team_name}</Pill>}
        </div>
        {reports.length > 0 && (
          <ul className="ml-4 border-l border-black/10 pl-5">
            {reports.map((r) => <Node key={r.id} m={r} />)}
          </ul>
        )}
      </li>
    );
  };

  if (members.length === 0) return null;
  return (
    <section className="card space-y-4 p-6 sm:p-8" aria-label="Organisation chart">
      <div>
        <h2 className="font-display text-xl font-extrabold tracking-tight">Organisation chart</h2>
        <p className="mt-1 text-sm text-mute">Who reports to whom. Set a person&apos;s lead under Edit place below.</p>
      </div>
      {top.length > 0 && <ul>{top.map((m) => <Node key={m.id} m={m} />)}</ul>}
      {unplaced.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-mute">Not placed under anyone yet</p>
          <ul>{unplaced.map((m) => <Node key={m.id} m={m} />)}</ul>
        </div>
      )}
    </section>
  );
}
