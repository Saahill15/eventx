"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "./ui/Button";
import { ErrorNote } from "./ui/bits";

/** Only follow same-site paths after signing in, so a crafted link cannot send people elsewhere. */
const safeNext = (next: string | undefined) => (next && next.startsWith("/") && !next.startsWith("//") ? next : "/");

export function AuthForm({ mode, next }: { mode: "login" | "signup"; next?: string }) {
  const { login, signup } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const isSignup = mode === "signup";
  const nextQuery = next ? `?next=${encodeURIComponent(next)}` : "";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      if (isSignup) await signup(name.trim(), email.trim(), password);
      else await login(email.trim(), password);
      router.push(safeNext(next));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md items-center px-6 py-10">
      <div className="glass-strong w-full rounded-[2rem] p-8 sm:p-10">
        <h1 className="font-display text-3xl font-black tracking-tight">{isSignup ? "Create your account" : "Welcome back"}</h1>
        <p className="mb-7 mt-2 text-neutral-500">{isSignup ? "One free account for every fest on HiveOut." : "Sign in to see your passes and register for events."}</p>
        <form onSubmit={submit} className="space-y-4" noValidate={false}>
          <ErrorNote>{error}</ErrorNote>
          {isSignup && (
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium">Full name</span>
              <input className="field" required autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
            </label>
          )}
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium">Email</span>
            <input className="field" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@college.edu" />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium">Password</span>
            <input className="field" type="password" required minLength={isSignup ? 8 : undefined} autoComplete={isSignup ? "new-password" : "current-password"} value={password} onChange={(e) => setPassword(e.target.value)} placeholder={isSignup ? "At least 8 characters" : "Your password"} />
          </label>
          <Button type="submit" size="lg" className="w-full" disabled={busy}>{busy ? "Please wait…" : isSignup ? "Create account" : "Sign in"}</Button>
        </form>
        <p className="mt-6 text-center text-sm text-neutral-500">
          {isSignup ? "Already have an account? " : "New to HiveOut? "}
          <Link href={`${isSignup ? "/login" : "/signup"}${nextQuery}`} className="font-semibold text-hive-ink">{isSignup ? "Sign in" : "Create an account"}</Link>
        </p>
      </div>
    </div>
  );
}
