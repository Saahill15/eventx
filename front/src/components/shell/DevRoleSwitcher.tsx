"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/**
 * Local development only. A small panel that signs you in as an admin, organiser, student or ordinary member in one
 * click. It renders nothing in a production build, and nothing unless the API answers /api/dev/status, which it does
 * only when the API runs on this machine with DEV_ROLE_SWITCHER=1.
 */
const PERSONAS = [
  { key: "admin", label: "Admin", home: "/admin" },
  { key: "organizer", label: "Organiser", home: "/dashboard" },
  { key: "student", label: "Student", home: "/" },
  { key: "user", label: "User", home: "/" },
] as const;

const OPEN_KEY = "dev_switcher_open";

export function DevRoleSwitcher() {
  const { user, loading, devSwitch, logout } = useAuth();
  const [available, setAvailable] = useState(false);
  const [open, setOpen] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (process.env.NODE_ENV === "production") return;
    try { if (window.localStorage.getItem(OPEN_KEY) === "0") setOpen(false); } catch { /* storage blocked */ }
    fetch(`${API_URL}/api/dev/status`, { cache: "no-store" })
      .then((res) => setAvailable(res.ok))
      .catch(() => setAvailable(false));
  }, []);

  if (process.env.NODE_ENV === "production" || !available || loading) return null;

  // Which persona is signed in right now
  const current = !user ? null : user.role === "admin" ? "admin" : user.role === "organizer" ? "organizer" : user.is_student_verified ? "student" : "user";

  const toggle = (next: boolean) => {
    setOpen(next);
    try { window.localStorage.setItem(OPEN_KEY, next ? "1" : "0"); } catch { /* ignore */ }
  };

  const go = async (key: (typeof PERSONAS)[number]) => {
    setBusy(key.key);
    setError("");
    try {
      await devSwitch(key.key);
      window.location.assign(key.home); // a full load, so nothing from the previous sign-in is left on screen
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not switch");
      setBusy(null);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => toggle(true)}
        className="fixed bottom-4 left-4 z-[90] rounded-full bg-ink px-4 py-2 text-xs font-semibold text-white shadow-[var(--shadow-pop)]"
        aria-label="Open the developer role switcher"
      >
        Dev · {current ?? "signed out"}
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 left-4 z-[90] w-60 rounded-2xl bg-ink p-3 text-white shadow-[var(--shadow-pop)]" role="region" aria-label="Developer role switcher">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-white/60">Dev · switch role</p>
        <button onClick={() => toggle(false)} className="text-xs text-white/60 hover:text-white" aria-label="Collapse">Hide</button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {PERSONAS.map((p) => (
          <button
            key={p.key}
            onClick={() => go(p)}
            disabled={busy !== null}
            aria-pressed={current === p.key}
            className={`rounded-xl px-3 py-2 text-sm font-semibold transition disabled:opacity-60 ${current === p.key ? "bg-white text-ink" : "bg-white/10 hover:bg-white/20"}`}
          >
            {busy === p.key ? "…" : p.label}
          </button>
        ))}
      </div>
      <button onClick={() => { logout(); window.location.assign("/"); }} disabled={!user || busy !== null} className="mt-2 w-full rounded-xl px-3 py-1.5 text-xs text-white/70 hover:bg-white/10 disabled:opacity-40">
        Sign out
      </button>
      {error && <p className="mt-2 text-xs text-red-300">{error}</p>}
    </div>
  );
}
