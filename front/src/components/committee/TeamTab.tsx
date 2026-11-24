"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { CommitteeTeam, FestInvite, FestRole, Member, Org } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Pill, Skeleton } from "@/components/ui/bits";
import { Field, Notice } from "@/components/ui/bits";
import { formatDay } from "@/lib/format";
import { OrgChart } from "./OrgChart";
import { TeamsPanel } from "./TeamsPanel";

const LABEL: Record<string, string> = { owner: "Festival director", core: "Core team", volunteer: "Volunteer" };
const HELP: Record<string, string> = { core: "Can manage events, registrations and the team", volunteer: "Helps on the day, no management access" };
const ORDER: Record<string, number> = { owner: 0, core: 1, volunteer: 2 };

/** Everyone someone leads, directly or through others. They cannot be picked as that person's own lead (it would loop). */
function below(members: Member[], id: number): Set<number> {
  const out = new Set<number>();
  const walk = (lead: number) => { for (const m of members) if (m.reports_to_id === lead && !out.has(m.id)) { out.add(m.id); walk(m.id); } };
  walk(id);
  return out;
}

function PlaceEditor({ slug, member, members, teams, onDone }: { slug: string; member: Member; members: Member[]; teams: CommitteeTeam[]; onDone: (changed: boolean) => void }) {
  const [title, setTitle] = useState(member.title ?? "");
  const [teamId, setTeamId] = useState(member.committee_team_id ? String(member.committee_team_id) : "");
  const [leadId, setLeadId] = useState(member.reports_to_id ? String(member.reports_to_id) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const blocked = below(members, member.id);
  const leads = members.filter((m) => m.id !== member.id && !blocked.has(m.id));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api(`/api/fests/${slug}/org/members/${member.id}`, { method: "PATCH", body: { title: title.trim() || null, committee_team_id: teamId ? Number(teamId) : null, reports_to_id: leadId ? Number(leadId) : null } });
      onDone(true);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save."); setBusy(false); }
  };

  return (
    <form onSubmit={save} className="mt-3 space-y-4 rounded-2xl bg-wash p-4">
      <ErrorNote>{error}</ErrorNote>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Title" hint="In your fest's words"><input className="field" value={title} maxLength={80} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Sponsorship Head" /></Field>
        <Field label="Team">
          <select className="field" value={teamId} onChange={(e) => setTeamId(e.target.value)}>
            <option value="">No team</option>
            {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </Field>
        <Field label="Reports to">
          <select className="field" value={leadId} onChange={(e) => setLeadId(e.target.value)}>
            <option value="">Nobody</option>
            {leads.map((m) => <option key={m.id} value={m.id}>{m.user_name}{m.title ? `, ${m.title}` : ""}</option>)}
          </select>
        </Field>
      </div>
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy}>{busy ? "Saving…" : "Save place"}</Button><Button size="sm" type="button" variant="ghost" onClick={() => onDone(false)}>Cancel</Button></div>
    </form>
  );
}

export function TeamTab({ slug, myRole }: { slug: string; myRole: FestRole }) {
  const { user } = useAuth();
  const [org, setOrg] = useState<Org | null>(null);
  const [invites, setInvites] = useState<FestInvite[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("volunteer");
  const [placing, setPlacing] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const canGrantCore = myRole === "owner" || myRole === "admin";
  const canEdit = myRole === "owner" || myRole === "core" || myRole === "admin";

  const load = useCallback(async () => {
    try { setOrg(await api<Org>(`/api/fests/${slug}/org`)); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load the team."); setOrg({ teams: [], members: [] }); }
  }, [slug]);
  const loadInvites = useCallback(() => { api<FestInvite[]>(`/api/fests/${slug}/invites`).then(setInvites).catch(() => {}); }, [slug]);
  useEffect(() => { load(); loadInvites(); }, [load, loadInvites]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/api/fests/${slug}/members`, { method: "POST", body: { email: email.trim(), role } });
      setEmail(""); setNotice("Invitation sent. They join the team once they accept it from their notifications."); await loadInvites();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not add that person."); }
    finally { setBusy(false); }
  };

  const withdraw = async (inv: FestInvite) => {
    setError(""); setNotice("");
    try { await api(`/api/fests/${slug}/invites/${inv.id}`, { method: "DELETE" }); await loadInvites(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not withdraw that invitation."); }
  };

  const remove = async (m: Member) => {
    if (!window.confirm(`Remove ${m.user_name ?? "this person"} from the team?`)) return;
    setError(""); setNotice("");
    try { await api(`/api/fests/${slug}/members/${m.user_id}`, { method: "DELETE" }); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not remove that person."); }
  };

  const canRemove = (m: Member) => m.user_id !== user?.id && (m.role === "owner" ? myRole === "admin" : m.role === "core" ? canGrantCore : true);
  const canPlace = (m: Member) => canEdit && (m.role !== "owner" || myRole === "owner" || myRole === "admin");

  return (
    <div className="max-w-4xl space-y-8">
      <form onSubmit={add} className="card space-y-4 p-6 sm:p-8">
        <h2 className="font-display text-xl font-extrabold tracking-tight">Add a team member</h2>
        <ErrorNote>{error}</ErrorNote>
        {notice && <Notice tone="ok">{notice}</Notice>}
        <div className="grid gap-4 sm:grid-cols-[1fr_240px]">
          <Field label="Their HiveOut email" hint="They need a HiveOut account. They confirm the invite, and must be a verified student to join.">
            <input className="field" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@college.edu" />
          </Field>
          <Field label="Access level" hint={HELP[role]}>
            <select className="field" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="volunteer">Volunteer</option>
              {canGrantCore && <option value="core">Core team</option>}
            </select>
          </Field>
        </div>
        <Button type="submit" disabled={busy}>{busy ? "Adding…" : "Add to team"}</Button>
      </form>

      {invites.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm font-semibold text-neutral-600">Waiting for them to accept</p>
          {invites.map((inv) => (
            <div key={inv.id} className="card flex items-center justify-between gap-4 p-4 sm:p-5">
              <div className="min-w-0">
                <p className="truncate font-semibold">{inv.user_name}</p>
                <p className="truncate text-sm text-neutral-500">{inv.user_email} · invited {formatDay(inv.created_at)}</p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <Pill tone="neutral">{LABEL[inv.role]}</Pill>
                <button onClick={() => withdraw(inv)} className="text-sm font-semibold text-red-600 hover:underline">Withdraw</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {org === null ? <Skeleton className="h-32" /> : (
        <>
          <OrgChart members={org.members} meId={user?.id} />
          <TeamsPanel slug={slug} teams={org.teams} members={org.members} canEdit={canEdit} reload={load} />

          <section className="space-y-3" aria-label="Everyone on the committee">
            <h2 className="font-display text-xl font-extrabold tracking-tight">Everyone</h2>
            {[...org.members].sort((a, b) => ORDER[a.role] - ORDER[b.role]).map((m) => (
              <div key={m.id} className="card p-4 sm:p-5">
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{m.user_name}{m.user_id === user?.id ? " (you)" : ""}</p>
                    <p className="truncate text-sm text-neutral-500">{[m.title, m.team_name, m.reports_to_name ? `reports to ${m.reports_to_name}` : null].filter(Boolean).join(" · ") || m.user_email}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <Pill tone="amber">{LABEL[m.role]}</Pill>
                    {canPlace(m) && <button onClick={() => setPlacing(placing === m.id ? null : m.id)} className="text-sm font-semibold underline underline-offset-4">{placing === m.id ? "Close" : "Edit place"}</button>}
                    {canRemove(m) && <button onClick={() => remove(m)} className="text-sm font-semibold text-red-600 hover:underline">Remove</button>}
                  </div>
                </div>
                {placing === m.id && <PlaceEditor slug={slug} member={m} members={org.members} teams={org.teams} onDone={(changed) => { setPlacing(null); if (changed) load(); }} />}
              </div>
            ))}
          </section>
        </>
      )}
    </div>
  );
}
