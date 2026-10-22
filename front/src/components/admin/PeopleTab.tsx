"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AdminCollege, AdminUser } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Pill, Skeleton } from "@/components/ui/bits";
import { Chips, useAction, when } from "./shared";

type RoleFilter = "all" | "user" | "organizer" | "admin";

/** Pick the partner colleges an organiser may list fests for. */
function CollegePicker({ colleges, initial, label, onSave, onCancel, busy }: { colleges: AdminCollege[]; initial: number[]; label: string; onSave: (ids: number[]) => void; onCancel: () => void; busy: boolean }) {
  const [ids, setIds] = useState<number[]>(initial);
  const partners = colleges.filter((c) => c.partner_status === "partner");
  const toggle = (id: number) => setIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  return (
    <div className="mt-4 rounded-2xl bg-wash p-4">
      <p className="mb-3 text-sm font-semibold">Which colleges can they list fests for?</p>
      {partners.length === 0 ? <p className="text-sm text-mute">No partner colleges yet. Mark a college as a partner in the Colleges tab first.</p> : (
        <div className="flex flex-wrap gap-2">
          {partners.map((c) => <button key={c.id} type="button" onClick={() => toggle(c.id)} aria-pressed={ids.includes(c.id)} className={`rounded-full px-4 py-2 text-sm font-medium transition ${ids.includes(c.id) ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)]"}`}>{c.name}</button>)}
        </div>
      )}
      <div className="mt-4 flex gap-2">
        <Button size="sm" disabled={busy || ids.length === 0} onClick={() => onSave(ids)}>{label}</Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

function PersonCard({ p, me, colleges, onDone }: { p: AdminUser; me: number | undefined; colleges: AdminCollege[]; onDone: () => void }) {
  const [picker, setPicker] = useState<"" | "promote" | "edit">("");
  const act = useAction(onDone);
  const isMe = p.id === me;
  const isAdmin = p.role === "admin";
  const names = p.college_ids.map((id) => colleges.find((c) => c.id === id)?.name).filter(Boolean).join(", ");
  const post = (path: string, body?: unknown) => act.run(async () => { await api(path, { method: "POST", body }); setPicker(""); });

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-semibold">{p.name} {isMe && <span className="text-xs font-normal text-mute">(you)</span>}</p>
          <p className="truncate text-sm text-mute">{p.email} · joined {when(p.created_at)}</p>
          {p.role === "organizer" && <p className="mt-1 text-xs text-mute">Colleges: {names || "none"}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone={p.role === "user" ? "neutral" : "amber"}>{p.role === "organizer" ? "Organiser" : isAdmin ? "Admin" : "Member"}</Pill>
          {!p.is_active && <Pill tone="red">Suspended</Pill>}
          {!isAdmin && !isMe && (
            <>
              {p.role === "user" && <Button size="sm" onClick={() => setPicker(picker === "promote" ? "" : "promote")}>Make organiser</Button>}
              {p.role === "organizer" && <Button size="sm" variant="outline" onClick={() => setPicker(picker === "edit" ? "" : "edit")}>Colleges</Button>}
              {p.role === "organizer" && <Button size="sm" variant="outline" disabled={act.busy} onClick={() => window.confirm(`Remove organiser access from ${p.name}?`) && post(`/api/admin/users/${p.id}/role`, { role: "user" })}>Remove organiser</Button>}
              <Button size="sm" variant="outline" disabled={act.busy} onClick={() => post(`/api/admin/users/${p.id}/sign-out`)}>Sign out</Button>
              <Button size="sm" variant="outline" disabled={act.busy} onClick={() => (p.is_active ? window.confirm(`Suspend ${p.name}? They will be signed out and cannot sign in.`) : true) && post(`/api/admin/users/${p.id}/active`, { is_active: !p.is_active })}>{p.is_active ? "Suspend" : "Reactivate"}</Button>
            </>
          )}
        </div>
      </div>
      {picker === "promote" && <CollegePicker colleges={colleges} initial={[]} label="Make organiser" busy={act.busy} onCancel={() => setPicker("")} onSave={(ids) => post(`/api/admin/users/${p.id}/role`, { role: "organizer", college_ids: ids })} />}
      {picker === "edit" && <CollegePicker colleges={colleges} initial={p.college_ids} label="Save colleges" busy={act.busy} onCancel={() => setPicker("")} onSave={(ids) => act.run(async () => { await api(`/api/admin/users/${p.id}/colleges`, { method: "PUT", body: { college_ids: ids } }); setPicker(""); })} />}
      <div className="mt-3"><ErrorNote>{act.error}</ErrorNote></div>
    </div>
  );
}

export function PeopleTab() {
  const { user } = useAuth();
  const [people, setPeople] = useState<AdminUser[] | null>(null);
  const [colleges, setColleges] = useState<AdminCollege[]>([]);
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<RoleFilter>("all");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    const params = new URLSearchParams({ q: query.trim() });
    if (role !== "all") params.set("role", role);
    api<AdminUser[]>(`/api/admin/users?${params}`).then((r) => { setPeople(r); setError(""); }).catch((e) => { setError(e instanceof Error ? e.message : "Could not load."); setPeople([]); });
  }, [query, role]);
  useEffect(() => { api<AdminCollege[]>("/api/admin/colleges").then(setColleges).catch(() => {}); }, []);
  useEffect(() => { const t = setTimeout(load, query ? 250 : 0); return () => clearTimeout(t); }, [load, query]);

  return (
    <div>
      <p className="mb-4 text-mute">Accounts start as members. Make someone an organiser for the partner colleges they represent, suspend an account, or end all of its sessions.</p>
      <input className="field mb-4" placeholder="Search by name or email" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search people" />
      <Chips value={role} onChange={setRole} options={[{ id: "all", label: "Everyone" }, { id: "user", label: "Members" }, { id: "organizer", label: "Organisers" }, { id: "admin", label: "Admins" }]} />
      <ErrorNote>{error}</ErrorNote>
      {people === null ? <Skeleton className="h-40" /> : people.length === 0 ? <EmptyState title="No one found" body="Try a different name or email." /> : (
        <div className="space-y-3">{people.map((p) => <PersonCard key={p.id} p={p} me={user?.id} colleges={colleges} onDone={load} />)}</div>
      )}
      {people && people.length === 50 && <p className="mt-4 text-center text-xs text-mute">Showing the 50 most recent. Search to narrow down.</p>}
    </div>
  );
}
