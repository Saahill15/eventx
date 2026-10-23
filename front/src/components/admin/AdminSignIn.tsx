"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Field, Notice } from "@/components/ui/bits";

/** Only follow paths inside the admin area after signing in. */
const adminNext = (next?: string) => (next && next.startsWith("/admin") && !next.startsWith("//") ? next : "/admin");

/** The only place admins sign in. It talks to a separate, stricter endpoint: five wrong tries lock it for 15 minutes, every attempt is logged, and it never says whether an email belongs to an admin. */
export function AdminSignIn({ next, expired }: { next?: string; expired?: boolean }) {
  const { user, loading, login, logout } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { if (!loading && user?.role === "admin") router.replace(adminNext(next)); }, [loading, user, router, next]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const result = await login(email.trim(), password, "admin");
      if (result.role !== "admin") { logout(); setError("Invalid credentials"); setBusy(false); return; }
      router.push(adminNext(next));
    } catch (err) { setError(err instanceof Error ? err.message : "Could not sign in."); setBusy(false); }
  };

  return (
    <div className="mx-auto flex min-h-[calc(100vh-9rem)] max-w-md items-center px-5">
      <form onSubmit={submit} className="card w-full space-y-5 p-8">
        <div>
          <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-ink text-white"><ShieldCheck className="h-6 w-6" /></span>
          <h1 className="font-display text-3xl font-semibold tracking-tight">Admin sign in</h1>
          <p className="mt-2 text-sm text-mute">For HiveOut administrators. Failed attempts are logged, and sessions end after 15 minutes without activity.</p>
        </div>
        <ErrorNote>{error}</ErrorNote>
        {expired && !error && <Notice tone="warn">You were signed out for your security. Please sign in again.</Notice>}
        <Field label="Email"><input className="field" type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Password"><input className="field" type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        <Button type="submit" size="lg" className="w-full" disabled={busy}>{busy ? "Please wait…" : "Sign in"}</Button>
        <p className="text-center text-sm"><Link href="/forgot-password?admin=1" className="font-semibold text-mute underline underline-offset-4 hover:text-ink">Forgot password?</Link></p>
      </form>
    </div>
  );
}
