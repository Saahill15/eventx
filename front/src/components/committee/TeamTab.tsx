"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { FestInvite, FestRole, Member, Org, TeamRole } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Pill, Skeleton } from "@/components/ui/bits";
import { Field, Notice } from "@/components/ui/bits";
import { formatDay } from "@/lib/format";
import { OrgChart } from "./OrgChart";
import { TeamsPanel } from "./TeamsPanel";
import { ACCESS, PlaceEditor, POSITION, TitleIdeas } from "./PlaceEditor";

const LABEL = ACCESS;
const HELP: Record<string, string> = { core: "Can manage events, registrations and the committee", volunteer: "Helps on the day, no management access" };
const ORDER: Record<string, number> = { owner: 0, core: 1, volunteer: 2 };

export function TeamTab({ slug, myRole }: { slug: string; myRole: FestRole }) {
  const { user } = useAuth();
  const [org, setOrg] = useState<Org | null>(null);
  const [invites, setInvites] = useState<FestInvite[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("volunteer");
  const [title, setTitle] = useState("");
  const [teamId, setTeamId] = useState("");
  const [position, setPosition] = useState<TeamRole>("member");
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
      await api(`/api/fests/${slug}/members`, { method: "POST", body: { email: email.trim(), role, ...(title.trim() ? { title: title.trim() } : {}), ...(teamId ? { committee_team_id: Number(teamId), team_role: position } : {}) } });
      setEmail(""); setTitle(""); setTeamId(""); setPosition("member"); setRole("volunteer");
      setNotice("Invitation sent. They join the committee, in the place you chose, once they accept it from their notifications."); await loadInvites();
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

  // A head normally has Core access, so choosing one offers it (the director can change it back). Co-heads and members start as volunteers
  const pickPosition = (p: TeamRole) => { setPosition(p); if (canGrantCore) setRole(p === "head" ? "core" : "volunteer"); };
  const pickTeam = (id: string) => { setTeamId(id); if (!id) pickPosition("member"); };
  const teams = org?.teams ?? [];
  const core = (org?.members ?? []).filter((m) => m.role === "owner" || m.role === "core");

  const canRemove = (m: Member) => m.user_id !== user?.id && (m.role === "owner" ? myRole === "admin" : m.role === "core" ? canGrantCore : true);
  const canPlace = (m: Member) => canEdit && (m.role !== "owner" || myRole === "owner" || myRole === "admin");

  return (
    <div className="max-w-4xl space-y-8">
      <section className="card space-y-3 p-6 sm:p-8" aria-label="How the committee works">
        <h2 className="font-display text-xl font-extrabold tracking-tight">How your committee is arranged</h2>
        <div className="grid gap-3 text-sm sm:grid-cols-3">
          <div><p className="font-semibold">Festival director and office-bearers</p><p className="text-mute">The director runs the fest on HiveOut. Give them the title your fest uses, such as Chairperson, and add a Vice Chairperson, General Secretary, Treasurer and so on.</p></div>
          <div><p className="font-semibold">Core team</p><p className="text-mute">The director, the office-bearers and, usually, the head of every team. They manage events, registrations and the committee.</p></div>
          <div><p className="font-semibold">Teams</p><p className="text-mute">Each led by a head, with co-heads and members. Heads usually have Core access; co-heads and members start as volunteers. The director can change anyone's.</p></div>
        </div>
      </section>

      <form onSubmit={add} className="card space-y-4 p-6 sm:p-8">
        <h2 className="font-display text-xl font-extrabold tracking-tight">Add someone to the committee</h2>
        <ErrorNote>{error}</ErrorNote>
        {notice && <Notice tone="ok">{notice}</Notice>}
        <div className="grid gap-4 sm:grid-cols-[1fr_260px]">
          <Field label="Their HiveOut email" hint="They need a HiveOut account. They confirm the invite, and must be a verified student to join.">
            <input className="field" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@college.edu" />
          </Field>
          <Field label="Title" hint="Optional. Pick one or write your own.">
            <input className="field" list="title-ideas" maxLength={80} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Vice Chairperson" /><TitleIdeas />
          </Field>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Team" hint="Optional">
            <select className="field" value={teamId} onChange={(e) => pickTeam(e.target.value)}>
              <option value="">No team yet</option>
              {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </Field>
          <Field label="Position in the team" hint={teamId ? undefined : "Pick a team first"}>
            <select className="field" value={teamId ? position : "member"} disabled={!teamId} onChange={(e) => pickPosition(e.target.value as TeamRole)}>
              <option value="member">Member</option><option value="co_head">Co-head</option><option value="head">Head</option>
            </select>
          </Field>
          <Field label="Access level" hint={HELP[role]}>
            <select className="field" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="volunteer">Volunteer</option>
              {canGrantCore && <option value="core">Core team</option>}
            </select>
          </Field>
        </div>
        {!canGrantCore && position === "head" && teamId && <p className="text-sm text-mute">Only the festival director can give Core team access, so they join as a volunteer and lead the team from there.</p>}
        <Button type="submit" disabled={busy}>{busy ? "Adding…" : "Send invitation"}</Button>
      </form>

      {invites.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm font-semibold text-neutral-600">Waiting for them to accept</p>
          {invites.map((inv) => (
            <div key={inv.id} className="card flex items-center justify-between gap-4 p-4 sm:p-5">
              <div className="min-w-0">
                <p className="truncate font-semibold">{inv.user_name}</p>
                <p className="truncate text-sm text-neutral-500">{inv.user_email}{inv.team_name ? ` · ${inv.team_role && inv.team_role !== "member" ? `${POSITION[inv.team_role]} of ` : "in "}${inv.team_name}` : ""} · invited {formatDay(inv.created_at)}</p>
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
          <section className="card space-y-3 p-6 sm:p-8" aria-label="Core team">
            <div>
              <h2 className="font-display text-xl font-extrabold tracking-tight">Core team <span className="font-normal text-mute">({core.length})</span></h2>
              <p className="mt-1 text-sm text-mute">Everyone who can manage the fest. Most are the heads of the teams below.</p>
            </div>
            <ul className="grid gap-2 sm:grid-cols-2">
              {core.map((m) => (
                <li key={m.id} className="flex flex-wrap items-center gap-x-2 rounded-xl bg-wash px-3 py-2 text-sm">
                  <span className="font-semibold">{m.user_name}</span>
                  <span className="text-mute">{[m.title, m.role === "owner" ? (m.title ? null : "Festival director") : m.team_name && m.team_role && m.team_role !== "member" ? `${POSITION[m.team_role]} of ${m.team_name}` : m.team_name ? `${m.team_name} team` : m.title ? null : "Core team"].filter(Boolean).join(" · ")}</span>
                  {m.role === "owner" && !m.title && m.user_id === user?.id && <button onClick={() => { setPlacing(m.id); window.setTimeout(() => document.getElementById(`member-${m.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 50); }} className="text-xs font-semibold underline underline-offset-4">Set your title</button>}
                </li>
              ))}
            </ul>
          </section>
          <TeamsPanel slug={slug} teams={org.teams} members={org.members} canEdit={canEdit} canGrantCore={canGrantCore} reload={load} />
          <OrgChart members={org.members} meId={user?.id} />

          <section className="space-y-3" aria-label="Everyone on the committee">
            <h2 className="font-display text-xl font-extrabold tracking-tight">Everyone</h2>
            {[...org.members].sort((a, b) => ORDER[a.role] - ORDER[b.role]).map((m) => (
              <div key={m.id} id={`member-${m.id}`} className="card p-4 sm:p-5">
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{m.user_name}{m.user_id === user?.id ? " (you)" : ""}</p>
                    <p className="truncate text-sm text-neutral-500">{[m.title, m.team_name, m.reports_to_name ? `reports to ${m.reports_to_name}` : null].filter(Boolean).join(" · ") || m.user_email}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    {m.team_role && m.team_role !== "member" && m.team_name && <Pill tone="green">{POSITION[m.team_role]} · {m.team_name}</Pill>}
                    <Pill tone="amber">{LABEL[m.role]}</Pill>
                    {canPlace(m) && <button onClick={() => setPlacing(placing === m.id ? null : m.id)} className="text-sm font-semibold underline underline-offset-4">{placing === m.id ? "Close" : "Edit place"}</button>}
                    {canRemove(m) && <button onClick={() => remove(m)} className="text-sm font-semibold text-red-600 hover:underline">Remove</button>}
                  </div>
                </div>
                {placing === m.id && <PlaceEditor slug={slug} member={m} members={org.members} teams={org.teams} canChangeAccess={canGrantCore} onDone={(changed) => { setPlacing(null); if (changed) load(); }} />}
              </div>
            ))}
          </section>
        </>
      )}
    </div>
  );
}
