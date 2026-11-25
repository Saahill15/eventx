"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { CommitteeTeam, Member } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Field, Pill } from "@/components/ui/bits";
import { POSITION } from "./PlaceEditor";

const MAX_CO_HEADS = 3;

/** Change a team: its name and description, who leads it, and what its leaders may do. */
function TeamEditor({ slug, team, members, canGrantCore, onDone }: { slug: string; team: CommitteeTeam; members: Member[]; canGrantCore: boolean; onDone: (changed: boolean) => void }) {
  const [name, setName] = useState(team.name);
  const [description, setDescription] = useState(team.description ?? "");
  const [head, setHead] = useState(team.head ? String(team.head.member_id) : "");
  const [coHeads, setCoHeads] = useState<number[]>(team.co_heads.map((c) => c.member_id));
  const [giveCore, setGiveCore] = useState(canGrantCore);
  const [manage, setManage] = useState(team.leaders_manage_team);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const toggleCo = (id: number) => setCoHeads((cur) => cur.includes(id) ? cur.filter((x) => x !== id) : cur.length >= MAX_CO_HEADS ? cur : [...cur, id]);
  const chooseHead = (id: string) => { setHead(id); if (id) setCoHeads((cur) => cur.filter((x) => x !== Number(id))); };
  const choosing = !!head || coHeads.length > 0;
  // Who would get Core access: the head, if they are a volunteer now. Co-heads keep the access they have
  const needCore = members.filter((m) => String(m.id) === head && m.role === "volunteer");

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api(`/api/fests/${slug}/org/teams/${team.id}`, { method: "PATCH", body: {
        name: name.trim(), description: description.trim() || null, leaders_manage_team: manage,
        head_member_id: head ? Number(head) : null, co_head_member_ids: coHeads, give_core_access: giveCore && canGrantCore,
      } });
      onDone(true);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save the team."); setBusy(false); }
  };

  return (
    <form onSubmit={save} className="space-y-4">
      <ErrorNote>{error}</ErrorNote>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Team name"><input className="field" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Head" hint="Leads the team. Choosing someone puts them in this team.">
          <select className="field" value={head} onChange={(e) => chooseHead(e.target.value)}>
            <option value="">No head yet</option>
            {members.map((m) => <option key={m.id} value={m.id}>{m.user_name}{m.committee_team_id && m.committee_team_id !== team.id ? ` (now in ${m.team_name})` : ""}</option>)}
          </select>
        </Field>
      </div>
      <Field label="What does this team do?"><input className="field" maxLength={300} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="One line the whole committee can read" /></Field>

      <fieldset>
        <legend className="mb-1.5 text-sm font-semibold">Co-heads <span className="font-normal text-mute">(up to {MAX_CO_HEADS})</span></legend>
        <div className="grid gap-1.5 sm:grid-cols-2">
          {members.filter((m) => String(m.id) !== head).map((m) => {
            const on = coHeads.includes(m.id);
            return (
              <label key={m.id} className={`flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-sm ring-1 ${on ? "ring-2 ring-ink" : "ring-black/10"} ${!on && coHeads.length >= MAX_CO_HEADS ? "opacity-50" : ""}`}>
                <input type="checkbox" checked={on} disabled={!on && coHeads.length >= MAX_CO_HEADS} onChange={() => toggleCo(m.id)} />
                <span className="truncate">{m.user_name}</span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <div className="space-y-2 rounded-2xl bg-white p-4 ring-1 ring-black/10">
        <p className="text-sm font-semibold">Permissions</p>
        {canGrantCore && !!head && (
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={giveCore} onChange={(e) => setGiveCore(e.target.checked)} />
            <span><strong>Give the head Core team access</strong><span className="block text-mute">They can then manage events, registrations and the committee. Co-heads keep the access they have.{needCore.length > 0 ? ` This changes ${needCore.map((m) => m.user_name).join(", ")} from volunteer to Core team.` : " The head already has it, or is the director."}</span></span>
          </label>
        )}
        {!canGrantCore && !!head && <p className="text-sm text-mute">Only the festival director can give someone Core team access.</p>}
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={manage} onChange={(e) => setManage(e.target.checked)} />
          <span><strong>The team&apos;s leaders run the team</strong><span className="block text-mute">The head and co-heads can bring people into the team, set their titles, give them tasks and edit the team&apos;s description, even without Core access.</span></span>
        </label>
      </div>
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy || !name.trim()}>{busy ? "Saving…" : "Save team"}</Button><Button size="sm" type="button" variant="ghost" onClick={() => onDone(false)}>Cancel</Button></div>
    </form>
  );
}

/** The teams of the committee (Sponsorship, PR, Logistics...) with their leaders and members. Staff add, edit and delete them. */
export function TeamsPanel({ slug, teams, members, canEdit, canGrantCore, reload }: { slug: string; teams: CommitteeTeam[]; members: Member[]; canEdit: boolean; canGrantCore: boolean; reload: () => void }) {
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); reload(); return true; } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); return false; } finally { setBusy(false); }
  };
  const add = async (e: React.FormEvent) => { e.preventDefault(); if (await run(() => api(`/api/fests/${slug}/org/teams`, { method: "POST", body: { name } }))) setName(""); };
  const remove = (t: CommitteeTeam) => { if (window.confirm(`Delete the ${t.name} team? Its people stay on the committee, without a team.`)) run(() => api(`/api/fests/${slug}/org/teams/${t.id}`, { method: "DELETE" })); };

  const people = (list: Member[]) => list.length === 0 ? <p className="text-sm text-mute">Nobody yet.</p> : (
    <ul className="space-y-1.5">{list.map((m) => (
      <li key={m.id} className="flex flex-wrap items-center gap-x-2 text-sm">
        <span className="font-medium">{m.user_name}</span>
        {m.team_role && m.team_role !== "member" && <Pill tone="amber">{POSITION[m.team_role]}</Pill>}
        {m.title && <span className="text-mute">· {m.title}</span>}
      </li>
    ))}</ul>
  );
  const unassigned = members.filter((m) => !m.committee_team_id);
  const order = { head: 0, co_head: 1, member: 2 } as const;

  return (
    <section className="card space-y-5 p-6 sm:p-8" aria-label="Teams">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-extrabold tracking-tight">Teams</h2>
          <p className="mt-1 text-sm text-mute">The parts of your committee, each with a head. Name them however your fest does.</p>
        </div>
        {canEdit && teams.length < 9 && <Button size="sm" variant="outline" disabled={busy} onClick={() => run(() => api(`/api/fests/${slug}/org/teams/suggested`, { method: "POST" }))}>Add the usual teams</Button>}
      </div>
      <ErrorNote>{error}</ErrorNote>

      {teams.length === 0 ? (
        <p className="text-sm text-mute">No teams yet. Add the usual set in one click, or create your own below.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {teams.map((t) => (
            <div key={t.id} className={`rounded-2xl bg-wash p-4 ${editing === t.id ? "sm:col-span-2" : ""}`}>
              {editing === t.id ? (
                <TeamEditor slug={slug} team={t} members={members} canGrantCore={canGrantCore} onDone={(changed) => { setEditing(null); if (changed) reload(); }} />
              ) : (
                <>
                  <div className="mb-2 flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-semibold">{t.name} <span className="font-normal text-mute">({t.member_count})</span></p>
                      {t.description && <p className="text-xs text-mute">{t.description}</p>}
                    </div>
                    {canEdit && <div className="flex shrink-0 gap-3 text-xs font-semibold"><button onClick={() => setEditing(t.id)} className="underline underline-offset-4">Edit team</button><button onClick={() => remove(t)} className="text-red-600 underline underline-offset-4">Delete</button></div>}
                  </div>
                  <p className="mb-2 text-sm">{t.head ? <><span className="text-mute">Head:</span> <span className="font-semibold">{t.head.name}</span></> : <span className="text-mute">No head yet{canEdit ? ". Use Edit team to choose one." : "."}</span>}{t.co_heads.length > 0 && <span className="text-mute"> · Co-head{t.co_heads.length > 1 ? "s" : ""}: <span className="font-semibold text-ink">{t.co_heads.map((c) => c.name).join(", ")}</span></span>}</p>
                  {people(members.filter((m) => m.committee_team_id === t.id).sort((a, b) => order[a.team_role ?? "member"] - order[b.team_role ?? "member"]))}
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {unassigned.length > 0 && teams.length > 0 && (
        <div><p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-mute">Not in a team yet</p>{people(unassigned)}</div>
      )}

      {canEdit && (
        <form onSubmit={add} className="flex flex-wrap items-end gap-3 border-t border-black/5 pt-5">
          <div className="min-w-[14rem] flex-1"><Field label="Add a team"><input className="field" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} placeholder="e.g. Hospitality" /></Field></div>
          <Button type="submit" disabled={busy || !name.trim()}>Add team</Button>
        </form>
      )}
    </section>
  );
}
