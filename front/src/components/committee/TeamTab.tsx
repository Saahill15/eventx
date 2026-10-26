"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { FestInvite, FestRole, Member } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Pill, Skeleton } from "@/components/ui/bits";
import { Field, Notice } from "@/components/ui/bits";
import { formatDay } from "@/lib/format";

const LABEL: Record<string, string> = { owner: "Festival director", core: "Core team", volunteer: "Volunteer" };
const HELP: Record<string, string> = { core: "Can manage events, registrations and the team", volunteer: "Helps on the day, no management access" };
const ORDER: Record<string, number> = { owner: 0, core: 1, volunteer: 2 };

export function TeamTab({ slug, myRole }: { slug: string; myRole: FestRole }) {
  const { user } = useAuth();
  const [members, setMembers] = useState<Member[] | null>(null);
  const [invites, setInvites] = useState<FestInvite[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("volunteer");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const canGrantCore = myRole === "owner" || myRole === "admin";

  const load = useCallback(async () => {
    try { setMembers(await api<Member[]>(`/api/fests/${slug}/members`)); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load the team."); setMembers([]); }
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

  return (
    <div className="space-y-8">
      <form onSubmit={add} className="card space-y-4 p-6 sm:p-8">
        <h2 className="font-display text-xl font-extrabold tracking-tight">Add a team member</h2>
        <ErrorNote>{error}</ErrorNote>
        {notice && <Notice tone="ok">{notice}</Notice>}
        <div className="grid gap-4 sm:grid-cols-[1fr_240px]">
          <Field label="Their HiveOut email" hint="They need a HiveOut account. They confirm the invite, and must be a verified student to join.">
            <input className="field" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@college.edu" />
          </Field>
          <Field label="Role" hint={HELP[role]}>
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

      {members === null ? <Skeleton className="h-20" /> : (
        <div className="space-y-3">
          {[...members].sort((a, b) => ORDER[a.role] - ORDER[b.role]).map((m) => (
            <div key={m.id} className="card flex items-center justify-between gap-4 p-4 sm:p-5">
              <div className="min-w-0">
                <p className="truncate font-semibold">{m.user_name}{m.user_id === user?.id ? " (you)" : ""}</p>
                <p className="truncate text-sm text-neutral-500">{m.user_email}</p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <Pill tone="amber">{LABEL[m.role]}</Pill>
                {canRemove(m) && <button onClick={() => remove(m)} className="text-sm font-semibold text-red-600 hover:underline">Remove</button>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
