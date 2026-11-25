"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { CommitteeTeam, Member, TeamRole } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Field } from "@/components/ui/bits";

export const POSITION: Record<TeamRole, string> = { head: "Head", co_head: "Co-head", member: "Member" };
/** Titles a committee usually has above its team heads. Only suggestions: any wording works. */
export const TITLE_IDEAS = ["Chairperson", "Vice Chairperson", "General Secretary", "Joint Secretary", "Treasurer", "Convenor", "Joint Convenor", "Sponsorship Head", "Event Coordinator"];
export function TitleIdeas() { return <datalist id="title-ideas">{TITLE_IDEAS.map((t) => <option key={t} value={t} />)}</datalist>; }

export const ACCESS: Record<string, string> = { owner: "Festival director", core: "Core team", volunteer: "Volunteer" };

/** Everyone someone leads, directly or through others. They cannot be picked as that person's own lead (it would loop). */
function below(members: Member[], id: number): Set<number> {
  const out = new Set<number>();
  const walk = (lead: number) => { for (const m of members) if (m.reports_to_id === lead && !out.has(m.id)) { out.add(m.id); walk(m.id); } };
  walk(id);
  return out;
}

/**
 * Where one person sits: title, team, position in the team, who they report to, and (for the director) their access level.
 * A team's own leaders see a shorter form: they can only set a title and a lead, inside their team.
 */
export function PlaceEditor({ slug, member, members, teams, canChangeAccess = false, leaderOnly = false, onDone }: {
  slug: string; member: Member; members: Member[]; teams: CommitteeTeam[]; canChangeAccess?: boolean; leaderOnly?: boolean; onDone: (changed: boolean) => void;
}) {
  const [title, setTitle] = useState(member.title ?? "");
  const [teamId, setTeamId] = useState(member.committee_team_id ? String(member.committee_team_id) : "");
  const [position, setPosition] = useState<TeamRole>(member.team_role ?? "member");
  const [leadId, setLeadId] = useState(member.reports_to_id ? String(member.reports_to_id) : "");
  const [access, setAccess] = useState<string>(member.role);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const blocked = below(members, member.id);
  const leads = members.filter((m) => m.id !== member.id && !blocked.has(m.id));
  const sameTeam = teamId === (member.committee_team_id ? String(member.committee_team_id) : "");

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const body: Record<string, unknown> = { title: title.trim() || null, reports_to_id: leadId ? Number(leadId) : null };
      if (!leaderOnly) {
        if (!sameTeam) body.committee_team_id = teamId ? Number(teamId) : null;
        if (teamId && (!sameTeam || position !== (member.team_role ?? "member"))) body.team_role = position;
      }
      await api(`/api/fests/${slug}/org/members/${member.id}`, { method: "PATCH", body });
      if (canChangeAccess && access !== member.role) await api(`/api/fests/${slug}/members`, { method: "POST", body: { user_id: member.user_id, role: access } });
      onDone(true);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save."); setBusy(false); }
  };

  return (
    <form onSubmit={save} className="mt-3 space-y-4 rounded-2xl bg-wash p-4">
      <ErrorNote>{error}</ErrorNote>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Title" hint="In your fest's words"><input className="field" list="title-ideas" value={title} maxLength={80} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Vice Chairperson" /><TitleIdeas /></Field>
        <Field label="Reports to">
          <select className="field" value={leadId} onChange={(e) => setLeadId(e.target.value)}>
            <option value="">Nobody</option>
            {leads.map((m) => <option key={m.id} value={m.id}>{m.user_name}{m.title ? `, ${m.title}` : ""}</option>)}
          </select>
        </Field>
        {!leaderOnly && (
          <>
            <Field label="Team">
              <select className="field" value={teamId} onChange={(e) => { setTeamId(e.target.value); setPosition("member"); }}>
                <option value="">No team</option>
                {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </Field>
            <Field label="Position in the team" hint={teamId ? undefined : "Pick a team first"}>
              <select className="field" value={teamId ? position : "member"} disabled={!teamId} onChange={(e) => setPosition(e.target.value as TeamRole)}>
                <option value="member">Member</option><option value="co_head">Co-head</option><option value="head">Head (leads the team)</option>
              </select>
            </Field>
          </>
        )}
        {canChangeAccess && member.role !== "owner" && (
          <Field label="Access level" hint="Core team can manage events, registrations and the committee">
            <select className="field" value={access} onChange={(e) => setAccess(e.target.value)}><option value="volunteer">Volunteer</option><option value="core">Core team</option></select>
          </Field>
        )}
      </div>
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</Button><Button size="sm" type="button" variant="ghost" onClick={() => onDone(false)}>Cancel</Button></div>
    </form>
  );
}
