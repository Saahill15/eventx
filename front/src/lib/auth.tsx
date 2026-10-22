"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { API_URL, api } from "./api";
import { OrganizerWelcome } from "@/components/OrganizerWelcome";
import type { AuthResult, SignupInput, User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, portal?: "admin") => Promise<AuthResult>;
  signup: (input: SignupInput) => Promise<AuthResult>;
  refresh: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

const IDLE_KEY = "idle_s";        // seconds of inactivity the server allows for this sign-in
const ACTIVE_KEY = "last_active"; // shared across tabs, so working in one tab keeps the others alive
const WARN_SECONDS = 60;
/** Used for a sign-in made before the timeout was stored. Ordinary members are not timed out on this device. */
const DEFAULT_IDLE: Record<string, number> = { admin: 15 * 60, organizer: 2 * 60 * 60 };

/** Where to send someone whose session ended: admins go back to the admin sign-in. */
const signInUrl = () => (window.location.pathname.startsWith("/admin") ? "/admin/login?expired=1" : "/login?expired=1");

const read = (key: string) => { try { return window.localStorage.getItem(key); } catch { return null; } };
const write = (key: string, value: string) => { try { window.localStorage.setItem(key, value); } catch { /* storage blocked */ } };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [warning, setWarning] = useState<number | null>(null);
  const lastPing = useRef(0);

  /** End the sign-in on the server (so a copied token stops working), then forget it here. */
  const logout = useCallback(() => {
    const token = read("token");
    if (token) fetch(`${API_URL}/api/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, keepalive: true }).catch(() => {});
    for (const k of ["token", IDLE_KEY, ACTIVE_KEY]) { try { window.localStorage.removeItem(k); } catch { /* ignore */ } }
    setUser(null);
    setWarning(null);
  }, []);

  const loadUser = useCallback(async () => {
    if (!read("token")) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api<User>("/api/users/me");
      if (!read(IDLE_KEY) && DEFAULT_IDLE[me.role]) write(IDLE_KEY, String(DEFAULT_IDLE[me.role]));
      setUser(me);
    } catch {
      window.localStorage.removeItem("token");
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
    const onExpired = () => { logout(); if (!window.location.pathname.endsWith("/login")) window.location.assign(signInUrl()); };
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, [loadUser, logout]);

  // Inactivity: sign out after the server's idle limit, with a warning first. Activity also tells the server we are still here.
  useEffect(() => {
    if (!user) return;
    const idleLimit = Number(read(IDLE_KEY)) || 0;
    if (!idleLimit || idleLimit > 24 * 60 * 60) return;
    if (!read(ACTIVE_KEY)) write(ACTIVE_KEY, String(Date.now()));
    let lastWrite = 0;
    const touch = () => {
      const now = Date.now();
      if (now - lastWrite < 3000) return;
      lastWrite = now;
      write(ACTIVE_KEY, String(now));
      if (now - lastPing.current > Math.min(idleLimit / 3, 5 * 60) * 1000) {
        lastPing.current = now;
        api("/api/users/me").catch(() => {}); // a 401 here ends the session through auth:expired
      }
    };
    const events = ["mousemove", "mousedown", "keydown", "scroll", "touchstart"] as const;
    events.forEach((e) => window.addEventListener(e, touch, { passive: true }));
    const timer = window.setInterval(() => {
      const idleFor = (Date.now() - (Number(read(ACTIVE_KEY)) || Date.now())) / 1000;
      if (idleFor >= idleLimit) { const url = signInUrl(); logout(); window.location.assign(url); }
      else if (idleLimit - idleFor <= WARN_SECONDS) setWarning(Math.ceil(idleLimit - idleFor));
      else setWarning(null);
    }, 1000);
    return () => { events.forEach((e) => window.removeEventListener(e, touch)); window.clearInterval(timer); };
  }, [user, logout]);

  const finish = useCallback(async (result: AuthResult) => {
    window.localStorage.setItem("token", result.access_token);
    if (result.idle_timeout_seconds) write(IDLE_KEY, String(result.idle_timeout_seconds)); else window.localStorage.removeItem(IDLE_KEY);
    write(ACTIVE_KEY, String(Date.now()));
    lastPing.current = Date.now();
    await loadUser();
    return result;
  }, [loadUser]);

  const login = useCallback(
    async (email: string, password: string, portal?: "admin") => finish(await api<AuthResult>(portal === "admin" ? "/api/auth/admin/login" : "/api/auth/login", { method: "POST", body: { email, password } })),
    [finish],
  );
  const signup = useCallback(
    async (input: SignupInput) => finish(await api<AuthResult>("/api/auth/signup", { method: "POST", body: input })),
    [finish],
  );

  const value = useMemo(() => ({ user, loading, login, signup, logout, refresh: loadUser }), [user, loading, login, signup, logout, loadUser]);
  return (
    <AuthContext.Provider value={value}>
      {children}
      <OrganizerWelcome />
      {warning !== null && (
        <div role="alertdialog" aria-live="assertive" className="fixed inset-x-4 bottom-6 z-[100] mx-auto flex max-w-md items-center justify-between gap-4 rounded-2xl bg-ink px-5 py-4 text-white shadow-[var(--shadow-pop)]">
          <p className="text-sm">Still there? You will be signed out in <strong>{warning}s</strong> because of inactivity.</p>
          <button onClick={() => { write(ACTIVE_KEY, String(Date.now())); setWarning(null); }} className="shrink-0 rounded-full bg-white px-4 py-2 text-sm font-semibold text-ink">Stay signed in</button>
        </div>
      )}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
