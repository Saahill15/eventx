"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { FestTask, Org, TaskStatus } from "@/lib/types";
import { formatDay } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Pill, Skeleton } from "@/components/ui/bits";

const COLUMNS: { id: TaskStatus; label: string }[] = [{ id: "todo", label: "To do" }, { id: "doing", label: "In progress" }, { id: "done", label: "Done" }];

function TaskForm({ slug, org, task, lockTeam, onDone }: { slug: string; org: Org; task: FestTask | null; lockTeam?: number; onDone: (changed: boolean) => void }) {
  const [f, setF] = useState({
    title: task?.title ?? "", description: task?.description ?? "", due: task?.due_date ?? "",
    assignee: task?.assignee_member_id ? String(task.assignee_member_id) : "", team: lockTeam ? String(lockTeam) : task?.committee_team_id ? String(task.committee_team_id) : "",
  });
  const people = lockTeam ? org.members.filter((m) => m.committee_team_id === lockTeam) : org.members;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF((x) => ({ ...x, [k]: e.target.value }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    const body = { title: f.title.trim(), description: f.description.trim() || null, due_date: f.due || null, assignee_member_id: f.assignee ? Number(f.assignee) : null, committee_team_id: f.team ? Number(f.team) : null };
    try {
      await api(task ? `/api/fests/${slug}/tasks/${task.id}` : `/api/fests/${slug}/tasks`, { method: task ? "PATCH" : "POST", body });
      onDone(true);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save the task."); setBusy(false); }
  };

  return (
    <form onSubmit={save} className="card space-y-4 p-5 sm:p-6">
      <h3 className="font-display text-lg font-semibold tracking-tight">{task ? "Edit task" : "New task"}</h3>
      <ErrorNote>{error}</ErrorNote>
      <Field label="What needs doing"><input className="field" required autoFocus maxLength={200} value={f.title} onChange={set("title")} placeholder="e.g. Print 200 posters" /></Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Who"><select className="field" value={f.assignee} onChange={set("assignee")}><option value="">Nobody yet</option>{people.map((m) => <option key={m.id} value={m.id}>{m.user_name}{m.title ? `, ${m.title}` : ""}</option>)}</select></Field>
        <Field label="Team"><select className="field" value={f.team} disabled={!!lockTeam} onChange={set("team")}><option value="">No team</option>{org.teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
        <Field label="Due"><input className="field" type="date" value={f.due} onChange={set("due")} /></Field>
      </div>
      <Field label="Details (optional)"><textarea className="field min-h-20" maxLength={2000} value={f.description} onChange={set("description")} /></Field>
      <div className="flex gap-2"><Button size="sm" type="submit" disabled={busy || !f.title.trim()}>{busy ? "Saving…" : task ? "Save task" : "Add task"}</Button><Button size="sm" type="button" variant="ghost" onClick={() => onDone(false)}>Cancel</Button></div>
    </form>
  );
}

/**
 * The committee's task board. Staff add, edit, assign and delete; anyone can see the board; the person a task is assigned to can
 * move it along. With `mineOnly` it is the short list a volunteer sees: just their own tasks.
 */
export function TasksTab({ slug, canManage, mineOnly = false, onlyTeamId }: { slug: string; canManage: boolean; mineOnly?: boolean; onlyTeamId?: number }) {
  const { user } = useAuth();
  const [tasks, setTasks] = useState<FestTask[] | null>(null);
  const [org, setOrg] = useState<Org>({ teams: [], members: [] });
  const [filter, setFilter] = useState<"all" | "mine" | "overdue">("all"); // the volunteer view is already narrowed to their own tasks by the server
  const [teamId, setTeamId] = useState("");
  const [editing, setEditing] = useState<FestTask | "new" | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const myMember = org.members.find((m) => m.user_id === user?.id);

  const load = useCallback(async () => {
    try {
      const [t, o] = await Promise.all([api<FestTask[]>(`/api/fests/${slug}/tasks${mineOnly ? "?assignee=me" : onlyTeamId ? `?team_id=${onlyTeamId}` : ""}`), canManage ? api<Org>(`/api/fests/${slug}/org`) : Promise.resolve({ teams: [], members: [] } as Org)]);
      setTasks(t); setOrg(o);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load the tasks."); setTasks([]); }
  }, [slug, mineOnly, onlyTeamId, canManage]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); await load(); } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); }
    setBusy(false);
  };
  const move = (t: FestTask, status: TaskStatus) => act(() => api(`/api/fests/${slug}/tasks/${t.id}`, { method: "PATCH", body: { status } }));
  const remove = (t: FestTask) => { if (window.confirm(`Delete "${t.title}"?`)) act(() => api(`/api/fests/${slug}/tasks/${t.id}`, { method: "DELETE" })); };

  if (tasks === null) return <Skeleton className="h-48" />;
  if (editing && canManage) return <div className="max-w-3xl"><TaskForm slug={slug} org={org} task={editing === "new" ? null : editing} lockTeam={onlyTeamId} onDone={(c) => { setEditing(null); if (c) load(); }} /></div>;

  const shown = tasks.filter((t) => (filter === "mine" ? t.assignee_member_id === myMember?.id : filter === "overdue" ? t.overdue : true) && (!teamId || t.committee_team_id === Number(teamId)));
  const mine = (t: FestTask) => canManage || (mineOnly && true) || (myMember && t.assignee_member_id === myMember.id);

  const Card = ({ t }: { t: FestTask }) => (
    <div className="rounded-2xl bg-white p-4 shadow-[var(--shadow-card)]">
      <p className="font-semibold">{t.title}</p>
      {t.description && <p className="mt-1 line-clamp-2 text-sm text-mute">{t.description}</p>}
      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-mute">
        <span>{t.assignee_name ?? "Unassigned"}</span>
        {t.due_date && <span className={t.overdue ? "font-semibold text-red-600" : ""}>· due {formatDay(t.due_date)}{t.overdue ? " (overdue)" : ""}</span>}
        {t.team_name && <Pill tone="neutral">{t.team_name}</Pill>}
      </div>
      {t.meeting_title && <p className="mt-1 text-xs text-mute">From the meeting &ldquo;{t.meeting_title}&rdquo;</p>}
      {mine(t) && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {t.status === "todo" && <Button size="sm" variant="outline" disabled={busy} onClick={() => move(t, "doing")}>Start</Button>}
          {t.status !== "done" && <Button size="sm" variant="outline" disabled={busy} onClick={() => move(t, "done")}>Done</Button>}
          {t.status === "done" && <Button size="sm" variant="ghost" disabled={busy} onClick={() => move(t, "todo")}>Reopen</Button>}
          {canManage && <><button onClick={() => setEditing(t)} className="px-1 text-xs font-semibold underline underline-offset-4">Edit</button>{!onlyTeamId && <button disabled={busy} onClick={() => remove(t)} className="px-1 text-xs font-semibold text-red-600 underline underline-offset-4">Delete</button>}</>}
        </div>
      )}
    </div>
  );

  return (
    <div className={mineOnly ? "space-y-4" : "space-y-5"}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        {mineOnly ? <h2 className="font-display text-lg font-semibold tracking-tight">Your tasks</h2> : (
          <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter tasks">
            {([["all", "All"], ["mine", "Mine"], ["overdue", "Overdue"]] as const).map(([id, label]) => (
              <button key={id} aria-pressed={filter === id} onClick={() => setFilter(id)} className={`rounded-full px-4 py-2 text-sm font-semibold transition ${filter === id ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)] hover:text-ink"}`}>{label}{id === "overdue" && tasks.some((t) => t.overdue) ? ` (${tasks.filter((t) => t.overdue).length})` : ""}</button>
            ))}
            {org.teams.length > 0 && <select aria-label="Filter by team" className="field !h-10 !w-auto" value={teamId} onChange={(e) => setTeamId(e.target.value)}><option value="">All teams</option>{org.teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select>}
          </div>
        )}
        {canManage && !mineOnly && <Button size="sm" onClick={() => setEditing("new")}><Plus className="h-4 w-4" /> New task</Button>}
      </div>
      <ErrorNote>{error}</ErrorNote>

      {tasks.length === 0 ? (
        <EmptyState title={mineOnly ? "Nothing assigned to you" : "No tasks yet"} body={mineOnly ? "When the committee gives you a task, it shows up here." : "Break the work into tasks, give each an owner and a date, and watch the board fill up."} action={canManage && !mineOnly ? <Button onClick={() => setEditing("new")}>Add the first task</Button> : undefined} />
      ) : (
        <div className={mineOnly ? "space-y-3" : "grid gap-4 md:grid-cols-3"}>
          {(mineOnly ? [{ id: "all" as const, label: "" }] : COLUMNS).map((col) => {
            const list = mineOnly ? shown.filter((t) => t.status !== "done") : shown.filter((t) => t.status === col.id);
            return (
              <section key={col.id} aria-label={mineOnly ? "Your open tasks" : col.label} className={mineOnly ? "space-y-3" : "space-y-3 rounded-3xl bg-wash p-3"}>
                {!mineOnly && <h3 className="px-2 pt-1 text-sm font-semibold">{col.label} <span className="font-normal text-mute">({list.length})</span></h3>}
                {list.length === 0 ? <p className="px-2 pb-2 text-sm text-mute">{mineOnly ? "You are all caught up." : "Nothing here."}</p> : list.map((t) => <Card key={t.id} t={t} />)}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
