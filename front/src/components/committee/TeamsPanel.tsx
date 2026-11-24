"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { CommitteeTeam, Member } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Field } from "@/components/ui/bits";

/** The teams of the committee (Sponsorship, PR, Logistics...) with who is in each. Staff can add, rename and delete them. */
export function TeamsPanel({ slug, teams, members, canEdit, reload }: { slug: string; teams: CommitteeTeam[]; members: Member[]; canEdit: boolean; reload: () => void }) {
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); reload(); return true; } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); return false; } finally { setBusy(false); }
  };
  const add = async (e: React.FormEvent) => { e.preventDefault(); if (await run(() => api(`/api/fests/${slug}/org/teams`, { method: "POST", body: { name } }))) setName(""); };
  const rename = async (t: CommitteeTeam) => { if (await run(() => api(`/api/fests/${slug}/org/teams/${t.id}`, { method: "PATCH", body: { name: draft } }))) setEditing(null); };
  const remove = (t: CommitteeTeam) => { if (window.confirm(`Delete the ${t.name} team? Its people stay on the committee, without a team.`)) run(() => api(`/api/fests/${slug}/org/teams/${t.id}`, { method: "DELETE" })); };

  const people = (list: Member[]) => list.length === 0 ? <p className="text-sm text-mute">Nobody yet.</p> : (
    <ul className="space-y-1.5">{list.map((m) => <li key={m.id} className="text-sm"><span className="font-medium">{m.user_name}</span>{m.title && <span className="text-mute"> · {m.title}</span>}</li>)}</ul>
  );
  const unassigned = members.filter((m) => !m.committee_team_id);

  return (
    <section className="card space-y-5 p-6 sm:p-8" aria-label="Teams">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-extrabold tracking-tight">Teams</h2>
          <p className="mt-1 text-sm text-mute">The parts of your committee. Name them however your fest does.</p>
        </div>
        {canEdit && teams.length < 9 && <Button size="sm" variant="outline" disabled={busy} onClick={() => run(() => api(`/api/fests/${slug}/org/teams/suggested`, { method: "POST" }))}>Add the usual teams</Button>}
      </div>
      <ErrorNote>{error}</ErrorNote>

      {teams.length === 0 ? (
        <p className="text-sm text-mute">No teams yet. Add the usual set in one click, or create your own below.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {teams.map((t) => (
            <div key={t.id} className="rounded-2xl bg-wash p-4">
              <div className="mb-2 flex items-start justify-between gap-2">
                {editing === t.id ? (
                  <form onSubmit={(e) => { e.preventDefault(); rename(t); }} className="flex w-full gap-2">
                    <input className="field" aria-label="Team name" autoFocus value={draft} maxLength={80} onChange={(e) => setDraft(e.target.value)} />
                    <Button size="sm" type="submit" disabled={busy || !draft.trim()}>Save</Button>
                    <Button size="sm" type="button" variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                  </form>
                ) : (
                  <>
                    <div className="min-w-0"><p className="font-semibold">{t.name} <span className="font-normal text-mute">({t.member_count})</span></p>{t.description && <p className="text-xs text-mute">{t.description}</p>}</div>
                    {canEdit && <div className="flex shrink-0 gap-3 text-xs font-semibold"><button onClick={() => { setEditing(t.id); setDraft(t.name); }} className="underline underline-offset-4">Rename</button><button onClick={() => remove(t)} className="text-red-600 underline underline-offset-4">Delete</button></div>}
                  </>
                )}
              </div>
              {people(members.filter((m) => m.committee_team_id === t.id))}
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
