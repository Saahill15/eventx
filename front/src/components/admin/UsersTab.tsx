"use client";

import { useCallback, useEffect, useState } from "react";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AdminCollege, AdminUser, AdminUserDetail } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Pill, Skeleton } from "@/components/ui/bits";
import { useAction, useCounts } from "./shared";

type RoleFilter = "all" | "user" | "organizer" | "admin";
type Permissions = { can_host_fests: boolean; can_host_city_events: boolean };

const ROLE_LABEL = { user: "Member", organizer: "Organiser", admin: "Admin" } as const;
const ROLE_TONE = { user: "neutral", organizer: "amber", admin: "green" } as const;
const FILTERS: { id: RoleFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "user", label: "Members" },
  { id: "organizer", label: "Organisers" },
  { id: "admin", label: "Admins" },
];

const initial = (name: string) => name.trim().charAt(0).toUpperCase() || "?";
const day = (iso: string) => new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

/** Two independent switches. Being an organiser never turns either one on by itself. */
function PermissionSwitches({ value, onChange, disabled }: { value: Permissions; onChange: (next: Permissions) => void; disabled?: boolean }) {
  const rows: { key: keyof Permissions; title: string; hint: string }[] = [
    { key: "can_host_fests", title: "Run fests", hint: "Create a fest for a college they are set up for, add events, and send it to HiveOut for review." },
    { key: "can_host_city_events", title: "List city events", hint: "Create standalone events such as concerts and workshops. HiveOut reviews each one." },
  ];
  return (
    <div className="divide-y divide-[var(--ws-border)] rounded-lg border border-[var(--ws-border)]">
      {rows.map((r) => (
        <label key={r.key} className="flex cursor-pointer items-start justify-between gap-4 p-4">
          <span className="min-w-0">
            <span className="block text-[14px] font-medium">{r.title}</span>
            <span className="mt-0.5 block text-[13px] text-mute">{r.hint}</span>
          </span>
          <input
            type="checkbox"
            role="switch"
            className="mt-1 h-5 w-9 shrink-0 cursor-pointer accent-[var(--ws-accent)]"
            checked={value[r.key]}
            disabled={disabled}
            onChange={(e) => onChange({ ...value, [r.key]: e.target.checked })}
            aria-label={r.title}
          />
        </label>
      ))}
    </div>
  );
}

function CollegeChips({ colleges, ids, onToggle }: { colleges: AdminCollege[]; ids: number[]; onToggle: (id: number) => void }) {
  const partners = colleges.filter((c) => c.partner_status === "partner");
  if (partners.length === 0) return <p className="text-sm text-mute">No partner colleges yet. Mark a college as a partner in the Colleges page first.</p>;
  return (
    <div className="flex flex-wrap gap-2">
      {partners.map((c) => (
        <button key={c.id} type="button" onClick={() => onToggle(c.id)} aria-pressed={ids.includes(c.id)} className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition ${ids.includes(c.id) ? "bg-ink text-white" : "bg-white text-mute ring-1 ring-[var(--ws-border)] hover:text-ink"}`}>
          {c.name}
        </button>
      ))}
    </div>
  );
}

/** Make a member an organiser: choose what they may do, and the colleges if they run fests. */
function PromoteForm({ colleges, busy, onCancel, onSave }: { colleges: AdminCollege[]; busy: boolean; onCancel: () => void; onSave: (body: Permissions & { college_ids: number[] }) => void }) {
  const [perms, setPerms] = useState<Permissions>({ can_host_fests: true, can_host_city_events: false });
  const [ids, setIds] = useState<number[]>([]);
  const toggle = (id: number) => setIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  const needsCollege = perms.can_host_fests && ids.length === 0;
  return (
    <div className="space-y-4 rounded-lg bg-wash p-4">
      <PermissionSwitches value={perms} onChange={setPerms} disabled={busy} />
      {perms.can_host_fests && (
        <div>
          <p className="mb-2 text-[13px] font-medium">Colleges they can list fests for</p>
          <CollegeChips colleges={colleges} ids={ids} onToggle={toggle} />
        </div>
      )}
      <div className="flex gap-2">
        <Button size="sm" disabled={busy || needsCollege} onClick={() => onSave({ ...perms, college_ids: perms.can_host_fests ? ids : [] })}>Make organiser</Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

/** Change the colleges an organiser may list fests for. */
function CollegeForm({ colleges, initialIds, busy, onCancel, onSave }: { colleges: AdminCollege[]; initialIds: number[]; busy: boolean; onCancel: () => void; onSave: (ids: number[]) => void }) {
  const [ids, setIds] = useState<number[]>(initialIds);
  const toggle = (id: number) => setIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  return (
    <div className="space-y-4 rounded-lg bg-wash p-4">
      <CollegeChips colleges={colleges} ids={ids} onToggle={toggle} />
      <div className="flex gap-2">
        <Button size="sm" disabled={busy || ids.length === 0} onClick={() => onSave(ids)}>Save colleges</Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

function Section({ title, children, show = true }: { title: string; children: React.ReactNode; show?: boolean }) {
  if (!show) return null;
  return (
    <section className="px-6 py-5">
      <h3 className="mb-3 text-[12px] font-semibold uppercase tracking-wider text-mute">{title}</h3>
      {children}
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="text-[12px] font-medium text-mute">{label}</p>
      <div className="mt-0.5 break-words text-[14px]">{children || <span className="text-mute">—</span>}</div>
    </div>
  );
}

/** Dates without a time (date of birth) are read as local dates, so they do not shift a day. Timestamps are shown as dates. */
const dateOnly = (iso: string | null) => {
  if (!iso) return null;
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
};
const dateTime = (iso: string | null) => (iso ? new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }) : null);

/** Name, phone, date of birth, study year and home college. Email, password and roles are not editable here. */
function ProfileForm({ detail, colleges, busy, onSaved, run }: { detail: AdminUserDetail; colleges: AdminCollege[]; busy: boolean; onSaved: () => void; run: (fn: () => Promise<unknown>) => Promise<boolean> }) {
  const [f, setF] = useState({ first_name: detail.first_name ?? "", last_name: detail.last_name ?? "", phone: detail.phone ?? "", date_of_birth: detail.date_of_birth ?? "", study_year: detail.study_year ? String(detail.study_year) : "", college_id: "" });
  const [editing, setEditing] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF((x) => ({ ...x, [k]: e.target.value }));
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const body: Record<string, unknown> = {
      first_name: f.first_name.trim(), last_name: f.last_name.trim(), phone: f.phone.trim() || null,
      date_of_birth: f.date_of_birth || null, study_year: f.study_year ? Number(f.study_year) : null,
    };
    if (f.college_id) body.college_id = Number(f.college_id);
    const ok = await run(async () => { await api(`/api/admin/users/${detail.id}/profile`, { method: "PATCH", body }); });
    if (ok) { setEditing(false); onSaved(); }
  };
  if (!editing) {
    return (
      <div className="space-y-4">
        <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
          <Row label="First name">{detail.first_name}</Row>
          <Row label="Last name">{detail.last_name}</Row>
          <Row label="Phone">{detail.phone}</Row>
          <Row label="Date of birth">{dateOnly(detail.date_of_birth)}</Row>
          <Row label="Study year">{detail.study_year ? `Year ${detail.study_year}` : null}</Row>
          <Row label="Home college">{detail.home_college}</Row>
        </div>
        <Button size="sm" variant="outline" onClick={() => setEditing(true)}>Edit details</Button>
      </div>
    );
  }
  return (
    <form onSubmit={save} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block"><span className="mb-1 block text-[12px] font-medium text-mute">First name</span><input className="field" required value={f.first_name} onChange={set("first_name")} /></label>
        <label className="block"><span className="mb-1 block text-[12px] font-medium text-mute">Last name</span><input className="field" required value={f.last_name} onChange={set("last_name")} /></label>
        <label className="block"><span className="mb-1 block text-[12px] font-medium text-mute">Phone</span><input className="field" type="tel" value={f.phone} onChange={set("phone")} /></label>
        <label className="block"><span className="mb-1 block text-[12px] font-medium text-mute">Date of birth</span><input className="field" type="date" value={f.date_of_birth} onChange={set("date_of_birth")} /></label>
        <label className="block"><span className="mb-1 block text-[12px] font-medium text-mute">Study year</span>
          <select className="field" value={f.study_year} onChange={set("study_year")}><option value="">Not set</option>{[1, 2, 3, 4, 5, 6].map((y) => <option key={y} value={y}>Year {y}</option>)}</select>
        </label>
        <label className="block"><span className="mb-1 block text-[12px] font-medium text-mute">Home college (leave blank to keep)</span>
          <select className="field" value={f.college_id} onChange={set("college_id")}><option value="">Keep {detail.home_college ?? "none"}</option>{colleges.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        </label>
      </div>
      <div className="flex gap-2">
        <Button size="sm" type="submit" disabled={busy}>Save details</Button>
        <Button size="sm" variant="ghost" type="button" onClick={() => setEditing(false)}>Cancel</Button>
      </div>
    </form>
  );
}

type TabId = "profile" | "security" | "student" | "access" | "teams";
const TABS: { id: TabId; label: string }[] = [
  { id: "profile", label: "Profile" },
  { id: "security", label: "Sign-in and security" },
  { id: "student", label: "Student" },
  { id: "access", label: "Access" },
  { id: "teams", label: "Fest teams" },
];

/** Everything about one account. Each change saves at once and then refreshes the list. */
function UserPanel({ user, colleges, isMe, onClose, onDone }: { user: AdminUser; colleges: AdminCollege[]; isMe: boolean; onClose: () => void; onDone: () => void }) {
  const act = useAction(onDone);
  const [form, setForm] = useState<"" | "promote" | "colleges">("");
  const [detail, setDetail] = useState<AdminUserDetail | null>(null);
  const [detailError, setDetailError] = useState("");
  const [tab, setTab] = useState<TabId>("profile");
  const isAdmin = user.role === "admin";
  const isOrganiser = user.role === "organizer";
  const names = user.college_ids.map((id) => colleges.find((c) => c.id === id)?.name).filter(Boolean).join(", ");
  const perms = { can_host_fests: user.can_host_fests, can_host_city_events: user.can_host_city_events };

  const loadDetail = useCallback(() => {
    api<AdminUserDetail>(`/api/admin/users/${user.id}`).then((d) => { setDetail(d); setDetailError(""); }).catch((e) => setDetailError(e instanceof Error ? e.message : "Could not load this account."));
  }, [user.id]);
  useEffect(() => { loadDetail(); }, [loadDetail, user.role, user.is_active, user.can_host_fests, user.can_host_city_events, user.college_ids.join(",")]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => { setForm(""); }, [user.id]);

  const refresh = () => { loadDetail(); onDone(); };
  const post = (path: string, body?: unknown) => act.run(async () => { await api(path, { method: "POST", body }); setForm(""); });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/25 p-4" onClick={onClose}>
      <aside role="dialog" aria-modal="true" aria-label={`Details for ${user.name}`} onClick={(e) => e.stopPropagation()} className="flex h-[min(640px,88vh)] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-[var(--shadow-pop)]">
        <header className="flex items-start justify-between gap-4 px-6 py-5">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-tint text-[18px] font-semibold text-tint-ink">{initial(user.name)}</div>
            <div className="min-w-0">
              <p className="truncate text-[18px] font-semibold">{user.name} {isMe && <span className="text-[13px] font-normal text-mute">(you)</span>}</p>
              <p className="truncate text-[13px] text-mute">{user.email}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <Pill tone={ROLE_TONE[user.role]}>{ROLE_LABEL[user.role]}</Pill>
                {!user.is_active && <Pill tone="red">Suspended</Pill>}
                {detail?.student.verified && <Pill tone="green">Verified student</Pill>}
              </div>
            </div>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-mute hover:bg-wash"><X className="h-4 w-4" /></button>
        </header>

        <nav role="tablist" aria-label="Account details" className="flex flex-wrap gap-x-1 border-b border-[var(--ws-border)] px-4">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)} className={`-mb-px whitespace-nowrap border-b-2 px-3 py-3 text-[14px] font-medium transition ${tab === t.id ? "border-ink text-ink" : "border-transparent text-mute hover:text-ink"}`}>{t.label}</button>
          ))}
        </nav>

        <div className="min-h-0 flex-1 overflow-y-auto">
        {detailError && <div className="px-6 pt-4"><ErrorNote>{detailError}</ErrorNote></div>}
        {!detail && !detailError && <div className="px-6 pb-6"><Skeleton className="h-40" /></div>}

        {detail && (
          <>
            <Section title="Profile" show={tab === "profile"}>
              {isMe ? (
                <p className="text-[14px] text-mute">This is your own account. Edit your details on your profile page.</p>
              ) : (
                <ProfileForm detail={detail} colleges={colleges} busy={act.busy} run={act.run} onSaved={refresh} />
              )}
              <div className="mt-5 grid gap-x-8 gap-y-4 border-t border-[var(--ws-border)] pt-5 sm:grid-cols-2">
                <Row label="Email">{detail.email}</Row>
                <Row label="Joined">{dateTime(detail.created_at)}</Row>
                <Row label="Terms accepted">{dateTime(detail.terms_accepted_at)}</Row>
                <Row label="Interests set">{detail.interests_set ? "Yes" : "Not yet"}</Row>
              </div>
            </Section>

            <Section title="Sign-in and security" show={tab === "security"}>
              <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
                <Row label="Password">{detail.has_password ? "Set" : "Not set (Google sign-in only)"}</Row>
                <Row label="Google account">{detail.google_linked ? "Linked" : "Not linked"}</Row>
                <Row label="Last active">{dateTime(detail.last_seen_at)}</Row>
                <Row label="Signed-in devices">{detail.active_sessions.length}</Row>
              </div>
              {detail.active_sessions.length > 0 && (
                <ul className="mt-4 divide-y divide-[var(--ws-border)] rounded-lg border border-[var(--ws-border)]">
                  {detail.active_sessions.slice(0, 5).map((s, i) => (
                    <li key={i} className="flex flex-wrap justify-between gap-2 p-3 text-[13px]">
                      <span className="truncate text-neutral-700">{s.user_agent ?? "Unknown device"}</span>
                      <span className="text-mute">{s.ip ?? "no IP"} · last seen {dateTime(s.last_seen_at)}</span>
                    </li>
                  ))}
                </ul>
              )}
              {detail.recent_sign_ins.length > 0 && (
                <div className="mt-5">
                  <p className="mb-2 text-[12px] font-medium text-mute">Recent sign-in attempts</p>
                  <ul className="divide-y divide-[var(--ws-border)] rounded-lg border border-[var(--ws-border)] text-[13px]">
                    {detail.recent_sign_ins.map((e, i) => (
                      <li key={i} className="flex flex-wrap justify-between gap-2 p-3">
                        <span className={e.success ? "text-emerald-700" : "text-red-700"}>{e.success ? "Signed in" : "Failed"} · {e.portal === "admin" ? "admin page" : "site"}{!e.success ? ` · ${e.reason}` : ""}</span>
                        <span className="text-mute">{dateTime(e.at)}{e.ip ? ` · ${e.ip}` : ""}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {!isMe && (
                <div className="mt-5 space-y-3">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-[14px] font-medium">Sign out everywhere</p>
                      <p className="text-[13px] text-mute">Ends every session, for example after a lost phone.</p>
                    </div>
                    <Button size="sm" variant="outline" disabled={act.busy} onClick={() => post(`/api/admin/users/${user.id}/sign-out`)}>Sign out</Button>
                  </div>
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-[14px] font-medium">{user.is_active ? "Suspend account" : "Reactivate account"}</p>
                      <p className="text-[13px] text-mute">{user.is_active ? "They are signed out and cannot sign in." : "They can sign in again."}</p>
                    </div>
                    <Button size="sm" variant={user.is_active ? "outline" : "amber"} disabled={act.busy} onClick={() => (user.is_active ? window.confirm(`Suspend ${user.name}? They will be signed out and cannot sign in.`) : true) && post(`/api/admin/users/${user.id}/active`, { is_active: !user.is_active })}>{user.is_active ? "Suspend" : "Reactivate"}</Button>
                  </div>
                </div>
              )}
              <p className="mt-4 text-[12px] text-mute">Passwords, email changes and Google sign-in are changed by the person themselves, for security.</p>
            </Section>

            <Section title="Student status" show={tab === "student"}>
              {detail.student.verified ? (
                <p className="text-[14px]">Verified until {dateOnly(detail.student.verified_until)}.</p>
              ) : (
                <p className="text-[14px] text-mute">Not verified as a student.</p>
              )}
              {detail.student.latest_method && (
                <div className="mt-3 grid gap-x-8 gap-y-3 sm:grid-cols-2">
                  <Row label="Latest check">{detail.student.latest_method === "email" ? "College email code" : "Uploaded document"}</Row>
                  <Row label="Status">{detail.student.latest_status}</Row>
                  <Row label="Submitted">{dateTime(detail.student.latest_at)}</Row>
                  <Row label="College">{detail.student.latest_college}</Row>
                  {detail.student.latest_reject_reason && <div className="sm:col-span-2"><Row label="Reason given">{detail.student.latest_reject_reason}</Row></div>}
                </div>
              )}
            </Section>

            <Section title="Role and organiser access" show={tab === "access"}>
              {!isOrganiser && !isAdmin && (
                form === "promote" ? (
                  <PromoteForm colleges={colleges} busy={act.busy} onCancel={() => setForm("")} onSave={(body) => post(`/api/admin/users/${user.id}/role`, { role: "organizer", ...body })} />
                ) : (
                  <div className="flex items-center justify-between gap-4">
                    <p className="text-[14px] text-mute">Member. Organisers can run fests and list city events, once switched on.</p>
                    {!isMe && <Button size="sm" onClick={() => setForm("promote")}>Make organiser</Button>}
                  </div>
                )
              )}
              {isOrganiser && !isMe && (
                <div className="flex items-center justify-between gap-4">
                  <p className="text-[14px]">Organiser</p>
                  <Button size="sm" variant="outline" disabled={act.busy} onClick={() => window.confirm(`Remove organiser access from ${user.name}?`) && post(`/api/admin/users/${user.id}/role`, { role: "user" })}>Remove organiser</Button>
                </div>
              )}
              {isAdmin && <p className="text-[14px] text-mute">Admin accounts keep their access and are not changed from this page.</p>}
              {isOrganiser && (
                <div className="mt-4 space-y-5">
                  <div>
                    <p className="mb-2 text-[12px] font-medium text-mute">Permissions</p>
                    <PermissionSwitches value={perms} disabled={act.busy || isMe} onChange={(next) => act.run(async () => { await api(`/api/admin/users/${user.id}/permissions`, { method: "PUT", body: next }); })} />
                  </div>
                  <div>
                    <p className="mb-2 text-[12px] font-medium text-mute">Colleges they can list fests for</p>
                    {form === "colleges" ? (
                      <CollegeForm colleges={colleges} initialIds={user.college_ids} busy={act.busy} onCancel={() => setForm("")} onSave={(ids) => act.run(async () => { await api(`/api/admin/users/${user.id}/colleges`, { method: "PUT", body: { college_ids: ids } }); setForm(""); })} />
                    ) : (
                      <div className="flex items-center justify-between gap-4">
                        <p className="text-[14px]">{names || <span className="text-mute">None assigned</span>}</p>
                        {!isMe && <Button size="sm" variant="outline" disabled={act.busy} onClick={() => setForm("colleges")}>Change</Button>}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </Section>

            <Section title="Fest teams" show={tab === "teams"}>
              {detail.fests.length === 0 ? (
                <p className="text-[14px] text-mute">Not on any fest team.</p>
              ) : (
                <ul className="divide-y divide-[var(--ws-border)] rounded-lg border border-[var(--ws-border)]">
                  {detail.fests.map((f) => (
                    <li key={f.slug} className="flex flex-wrap items-center justify-between gap-2 p-3">
                      <span className="text-[14px] font-medium">{f.name}</span>
                      <span className="flex gap-1.5"><Pill tone="neutral">{f.my_role}</Pill><Pill tone="neutral">{f.review_status.replace("_", " ")}</Pill></span>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          </>
        )}

        <div className="px-6 pb-6"><ErrorNote>{act.error}</ErrorNote></div>
        </div>
      </aside>
    </div>
  );
}

function AccessCell({ u }: { u: AdminUser }) {
  if (u.role !== "organizer") return <span className="text-mute">—</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      <Pill tone={u.can_host_fests ? "green" : "neutral"}>{u.can_host_fests ? "Fests" : "No fests"}</Pill>
      <Pill tone={u.can_host_city_events ? "green" : "neutral"}>{u.can_host_city_events ? "City events" : "No city events"}</Pill>
    </div>
  );
}

export function UsersTab() {
  const { user } = useAuth();
  const counts = useCounts();
  const [people, setPeople] = useState<AdminUser[] | null>(null);
  const [colleges, setColleges] = useState<AdminCollege[]>([]);
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<RoleFilter>("all");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<AdminUser | null>(null);

  const load = useCallback(() => {
    const params = new URLSearchParams({ q: query.trim() });
    if (role !== "all") params.set("role", role);
    api<AdminUser[]>(`/api/admin/users?${params}`)
      .then((rows) => {
        setPeople(rows); setError("");
        // Keep the open panel in step with the list after each change
        setSelected((cur) => (cur ? rows.find((r) => r.id === cur.id) ?? cur : cur));
      })
      .catch((e) => { setError(e instanceof Error ? e.message : "Could not load users."); setPeople([]); });
  }, [query, role]);
  useEffect(() => { api<AdminCollege[]>("/api/admin/colleges").then(setColleges).catch(() => {}); }, []);
  useEffect(() => { const t = setTimeout(load, query ? 250 : 0); return () => clearTimeout(t); }, [load, query]);

  const total = counts ? counts.members + counts.organizers + counts.admins : null;
  const filters = FILTERS.map((f) => ({
    ...f,
    count: counts ? (f.id === "all" ? total! : f.id === "user" ? counts.members : f.id === "organizer" ? counts.organizers : counts.admins) : undefined,
  }));

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Filter by role">
          {filters.map((f) => (
            <button key={f.id} role="tab" aria-selected={role === f.id} onClick={() => setRole(f.id)} className={`inline-flex h-9 items-center gap-2 rounded-lg px-3.5 text-[13px] font-medium transition ${role === f.id ? "bg-ink text-white" : "text-mute hover:bg-wash hover:text-ink"}`}>
              {f.label}
              {f.count !== undefined && <span className={`tabular-nums ${role === f.id ? "text-white/70" : "text-mute"}`}>{f.count}</span>}
            </button>
          ))}
        </div>
        <input className="field h-10 lg:w-80" placeholder="Search name or email" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search users" />
      </div>

      <ErrorNote>{error}</ErrorNote>

      {people === null ? <Skeleton className="h-72" /> : people.length === 0 ? <EmptyState title="No users found" body="Try a different name or email, or another role." /> : (
        <div className="card overflow-hidden">
          <table className="hidden w-full text-left text-[14px] md:table">
            <thead className="border-b border-[var(--ws-border)] bg-wash/60 text-[12px] font-semibold uppercase tracking-wider text-mute">
              <tr>
                <th className="px-5 py-3 font-semibold">User</th>
                <th className="px-5 py-3 font-semibold">Role</th>
                <th className="px-5 py-3 font-semibold">Access</th>
                <th className="px-5 py-3 font-semibold">Colleges</th>
                <th className="px-5 py-3 font-semibold">Status</th>
                <th className="px-5 py-3 font-semibold">Joined</th>
                <th className="px-5 py-3"><span className="sr-only">Manage</span></th>
              </tr>
            </thead>
            <tbody>
              {people.map((u) => {
                const isMe = u.id === user?.id;
                const names = u.college_ids.map((id) => colleges.find((c) => c.id === id)?.name).filter(Boolean).join(", ");
                return (
                  <tr key={u.id} className="border-b border-[var(--ws-border)] last:border-0 hover:bg-black/[0.015]">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-wash text-[13px] font-semibold text-neutral-700">{initial(u.name)}</div>
                        <div className="min-w-0">
                          <p className="truncate font-medium">{u.name}{isMe && <span className="ml-1.5 text-[12px] font-normal text-mute">(you)</span>}</p>
                          <p className="truncate text-[13px] text-mute">{u.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3.5"><Pill tone={ROLE_TONE[u.role]}>{ROLE_LABEL[u.role]}</Pill></td>
                    <td className="px-5 py-3.5"><AccessCell u={u} /></td>
                    <td className="max-w-[220px] px-5 py-3.5 text-[13px]">{u.role === "organizer" ? (names ? <span className="line-clamp-2">{names}</span> : <span className="text-mute">None</span>) : <span className="text-mute">—</span>}</td>
                    <td className="px-5 py-3.5">{u.is_active ? <span className="text-[13px] text-neutral-600">Active</span> : <Pill tone="red">Suspended</Pill>}</td>
                    <td className="whitespace-nowrap px-5 py-3.5 text-[13px] text-mute">{day(u.created_at)}</td>
                    <td className="px-5 py-3.5 text-right">
                      {u.role === "admin" || isMe ? null : <Button size="sm" variant="outline" onClick={() => setSelected(u)}>Manage</Button>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <ul className="divide-y divide-[var(--ws-border)] md:hidden">
            {people.map((u) => {
              const isMe = u.id === user?.id;
              return (
                <li key={u.id} className="space-y-3 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-wash text-[13px] font-semibold text-neutral-700">{initial(u.name)}</div>
                      <div className="min-w-0">
                        <p className="truncate font-medium">{u.name}{isMe && <span className="ml-1.5 text-[12px] font-normal text-mute">(you)</span>}</p>
                        <p className="truncate text-[13px] text-mute">{u.email}</p>
                      </div>
                    </div>
                    <Pill tone={ROLE_TONE[u.role]}>{ROLE_LABEL[u.role]}</Pill>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <AccessCell u={u} />
                    {!u.is_active && <Pill tone="red">Suspended</Pill>}
                  </div>
                  {u.role !== "admin" && !isMe && <Button size="sm" variant="outline" className="w-full" onClick={() => setSelected(u)}>Manage</Button>}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {people && people.length === 50 && <p className="text-center text-[13px] text-mute">Showing the 50 most recent. Search to narrow down.</p>}

      {selected && (
        <UserPanel user={selected} colleges={colleges} isMe={selected.id === user?.id} onClose={() => setSelected(null)} onDone={load} />
      )}
    </div>
  );
}
