"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AuthSession } from "@/lib/types";
import { Button } from "./ui/Button";
import { StudentVerification } from "./StudentVerification";
import { ErrorNote, Field, Notice, Pill } from "./ui/bits";

const when = (iso: string) => new Date(iso + "Z").toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
const device = (ua: string | null) => (ua ? (/iPhone|Android|Mobile/i.test(ua) ? "Phone" : /Mac|Windows|Linux/i.test(ua) ? "Computer" : "Browser") + (/Chrome\//.test(ua) && !/Edg/.test(ua) ? " · Chrome" : /Safari\//.test(ua) && !/Chrome/.test(ua) ? " · Safari" : /Firefox\//.test(ua) ? " · Firefox" : "") : "Unknown device");

/** Name and mobile number. The email is the sign-in and cannot be changed here. */
function Details() {
  const { user, refresh } = useAuth();
  const [f, setF] = useState({ first_name: user?.first_name ?? "", last_name: user?.last_name ?? "", phone: user?.phone ?? "" });
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => { setSaved(false); setF((x) => ({ ...x, [k]: e.target.value })); };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api("/api/users/me", { method: "PATCH", body: { first_name: f.first_name, last_name: f.last_name, phone: f.phone || null } });
      await refresh(); setSaved(true);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save."); }
    setBusy(false);
  };

  return (
    <form onSubmit={save} className="card space-y-4 p-7">
      <h2 className="font-display text-xl font-semibold tracking-tight">Your details</h2>
      <ErrorNote>{error}</ErrorNote>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="First name"><input className="field" required value={f.first_name} onChange={set("first_name")} /></Field>
        <Field label="Last name"><input className="field" required value={f.last_name} onChange={set("last_name")} /></Field>
        <Field label="Mobile number"><input className="field" type="tel" value={f.phone} onChange={set("phone")} /></Field>
        <Field label="Email" hint="Your sign-in. It cannot be changed."><input className="field" value={user?.email ?? ""} disabled /></Field>
      </div>
      <div className="flex items-center gap-3"><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</Button>{saved && <span className="text-sm font-medium text-emerald-700">Saved</span>}</div>
    </form>
  );
}

function Security() {
  const router = useRouter();
  const { logout } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [sessions, setSessions] = useState<AuthSession[] | null>(null);

  const load = useCallback(() => { api<AuthSession[]>("/api/auth/sessions").then(setSessions).catch(() => setSessions([])); }, []);
  useEffect(load, [load]);

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(""); setNote("");
    try {
      await api("/api/users/me/password", { method: "POST", body: { current_password: current, new_password: next } });
      setCurrent(""); setNext(""); setNote("Password changed. Your other devices were signed out."); load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not change the password."); }
    setBusy(false);
  };
  const end = async (id: string) => { await api(`/api/auth/sessions/${id}`, { method: "DELETE" }).catch(() => {}); load(); };

  const { user } = useAuth();
  return (
    <>
      {user && !user.has_password ? (
        <div className="card space-y-3 p-7">
          <h2 className="font-display text-xl font-semibold tracking-tight">Password</h2>
          <p className="text-sm text-mute">You sign in with Google. To also sign in with your email and a password, set one with a reset link.</p>
          <Button href="/forgot-password" variant="outline">Set a password</Button>
        </div>
      ) : (
      <form onSubmit={changePassword} className="card space-y-4 p-7">
        <h2 className="font-display text-xl font-semibold tracking-tight">Change password</h2>
        <ErrorNote>{error}</ErrorNote>
        {note && <Notice tone="ok">{note}</Notice>}
        <Field label="Current password"><input className="field" type="password" required autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} /></Field>
        <Field label="New password" hint="At least 8 characters."><input className="field" type="password" required minLength={8} autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} /></Field>
        <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Change password"}</Button>
      </form>
      )}
      {user?.google_linked && <p className="px-1 text-sm text-mute">Your Google account is linked: you can also sign in with Google.</p>}

      <div className="card space-y-4 p-7">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-display text-xl font-semibold tracking-tight">Where you are signed in</h2>
          <Button size="sm" variant="outline" onClick={async () => { await api("/api/auth/logout-all", { method: "POST" }).catch(() => {}); logout(); router.push("/login"); }}>Sign out everywhere</Button>
        </div>
        {sessions === null ? <p className="text-sm text-mute">Loading…</p> : (
          <ul className="divide-y divide-black/5">
            {sessions.map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="font-semibold">{device(s.user_agent)} {s.current && <Pill tone="green">This device</Pill>}</p>
                  <p className="text-xs text-mute">Signed in {when(s.created_at)} · last active {when(s.last_seen_at)}{s.ip ? ` · ${s.ip}` : ""}</p>
                </div>
                {!s.current && <button onClick={() => end(s.id)} className="text-sm font-semibold text-red-600 hover:underline">End</button>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

export function ProfileView() {
  const { user, logout } = useAuth();
  const router = useRouter();
  if (!user) return null;

  return (
    <div className="space-y-5">
      <div className="card flex items-center gap-5 p-7">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-ink font-display text-2xl font-bold text-white">{user.name.charAt(0).toUpperCase()}</div>
        <div className="min-w-0">
          <p className="truncate font-display text-2xl font-semibold tracking-tight">{user.name}</p>
          <p className="truncate text-mute">{user.email}</p>
          <div className="mt-2"><Pill tone="amber">{user.role === "organizer" ? "Organiser" : user.role === "admin" ? "Admin" : "Member"}</Pill></div>
        </div>
      </div>
      {user.role === "admin" && <Notice tone="info">Admin sessions end after 15 minutes without activity and after 8 hours at most.</Notice>}
      <Details />
      {user.role !== "admin" && <StudentVerification />}
      <Security />
      <Button variant="outline" onClick={() => { logout(); router.push("/"); }}>Sign out</Button>
    </div>
  );
}
