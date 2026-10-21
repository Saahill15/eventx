"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
import type { AuthResult, User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<AuthResult>;
  signup: (name: string, email: string, password: string) => Promise<AuthResult>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    window.localStorage.removeItem("token");
    setUser(null);
  }, []);

  const loadUser = useCallback(async () => {
    if (!window.localStorage.getItem("token")) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api<User>("/api/users/me"));
    } catch {
      window.localStorage.removeItem("token");
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
    const onExpired = () => logout();
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, [loadUser, logout]);

  const finish = useCallback(async (result: AuthResult) => {
    window.localStorage.setItem("token", result.access_token);
    await loadUser();
    return result;
  }, [loadUser]);

  const login = useCallback(
    async (email: string, password: string) => finish(await api<AuthResult>("/api/auth/login", { method: "POST", body: { email, password } })),
    [finish],
  );
  const signup = useCallback(
    async (name: string, email: string, password: string) => finish(await api<AuthResult>("/api/auth/signup", { method: "POST", body: { name, email, password } })),
    [finish],
  );

  const value = useMemo(() => ({ user, loading, login, signup, logout }), [user, loading, login, signup, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
