"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Member, Org } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Field, Pill, Skeleton } from "@/components/ui/bits";
import { PlaceEditor, POSITION } from "./PlaceEditor";
import { TasksTab } from "./TasksTab";

/**
 * What a team's head or co-head sees when they do not have Core team access: their own team, with its people and tasks.
 * Nothing here for anyone else. The core team's committee page is the full version.
 */
export function MyTeamPanel({ slug }: { slug: string }) {
  const { user } = useAuth();
  const [org, setOrg] = useState<Org | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [desc, setDesc] = useState<string | null>(null);
  const [adding, setAdding] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => { api<Org>(`/api/fests/${slug}/org`).then(setOrg).catch(() => setOrg({ teams: [], members: [] })); }, [slug]);
  useEffect(() => { load(); }, [load]);

  const me = org?.members.find((m) => m.user_id === user?.id);
  const team = org?.teams.find((t) => t.id === me?.committee_team_id);
  if (org === null) return <Skeleton className="h-24" />;
  if (!me || !team || me.team_role === "member" || !team.leaders_manage_team) return null;

  const mine = org.members.filter((m) => m.committee_team_id === team.id);
  const free = org.members.filter((m) => !m.committee_team_id && m.role !== "owner");
  const run = async (fn: () => Promise<unknown>) => { setBusy(true); setError(""); try { await fn(); load(); return true; } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); return false; } finally { setBusy(false); } };
  const place = (m: Member, teamId: number | null) => run(() => api(`/api/fests/${slug}/org/members/${m.id}`, { method: "PATCH", body: { committee_team_id: teamId } }));

  return (
    <div className="mb-8 space-y-6">
      <section className="card space-y-4 p-6" aria-label="Your team">
        <div>
          <h2 className="font-display text-xl font-extrabold tracking-tight">{team.name} <Pill tone="green">You are the {POSITION[me.team_role ?? "member"].toLowerCase()}</Pill></h2>
          <p className="mt-1 text-sm text-mute">You run this team: bring people in, set their titles and give them tasks.</p>
        </div>
        <ErrorNote>{error}</ErrorNote>
        {desc === null ? (
          <p className="text-sm">{team.description || <span className="text-mute">No description yet.</span>} <button onClick={() => setDesc(team.description ?? "")} className="font-semibold underline underline-offset-4">Edit</button></p>
        ) : (
          <form onSubmit={async (e) => { e.preventDefault(); if (await run(() => api(`/api/fests/${slug}/org/teams/${team.id}`, { method: "PATCH", body: { description: desc.trim() || null } }))) setDesc(null); }} className="flex flex-wrap gap-2">
            <input className="field min-w-[14rem] flex-1" maxLength={300} value={desc} onChange={(e) => setDesc(e.target.value)} aria-label="Team description" />
            <Button size="sm" type="submit" disabled={busy}>Save</Button><Button size="sm" type="button" variant="ghost" onClick={() => setDesc(null)}>Cancel</Button>
          </form>
        )}
        <ul className="space-y-2">
          {mine.map((m) => (
            <li key={m.id} className="rounded-2xl bg-wash px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm"><span className="font-semibold">{m.user_name}</span>{m.team_role && m.team_role !== "member" && <> <Pill tone="amber">{POSITION[m.team_role]}</Pill></>}{m.title && <span className="text-mute"> · {m.title}</span>}</p>
                <div className="flex gap-3 text-sm font-semibold">
                  <button onClick={() => setEditing(editing === m.id ? null : m.id)} className="underline underline-offset-4">{editing === m.id ? "Close" : "Title"}</button>
                  {m.team_role === "member" && <button disabled={busy} onClick={() => window.confirm(`Take ${m.user_name} out of the team?`) && place(m, null)} className="text-red-600 hover:underline">Remove</button>}
                </div>
              </div>
              {editing === m.id && <PlaceEditor slug={slug} member={m} members={org.members} teams={org.teams} leaderOnly onDone={(c) => { setEditing(null); if (c) load(); }} />}
            </li>
          ))}
        </ul>
        {free.length > 0 && (
          <form onSubmit={async (e) => { e.preventDefault(); const m = org.members.find((x) => x.id === Number(adding)); if (m && await place(m, team.id)) setAdding(""); }} className="flex flex-wrap items-end gap-3 border-t border-black/5 pt-4">
            <div className="min-w-[14rem] flex-1"><Field label="Bring someone into the team" hint="From people on the committee who are not in a team yet"><select className="field" value={adding} onChange={(e) => setAdding(e.target.value)}><option value="">Choose a person</option>{free.map((m) => <option key={m.id} value={m.id}>{m.user_name}</option>)}</select></Field></div>
            <Button type="submit" disabled={busy || !adding}>Add to team</Button>
          </form>
        )}
      </section>
      <div><h3 className="mb-3 font-display text-lg font-semibold tracking-tight">Tasks for your team</h3><TasksTab slug={slug} canManage onlyTeamId={team.id} /></div>
    </div>
  );
}
