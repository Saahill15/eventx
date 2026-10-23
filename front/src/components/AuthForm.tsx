"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { QrCode, Ticket, Users } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Button } from "./ui/Button";
import { ErrorNote, Field, Notice } from "./ui/bits";
import { GoogleButton } from "./GoogleButton";

/** Only follow same-site paths after signing in, so a crafted link cannot send people elsewhere. */
const safeNext = (next: string | undefined) => (next && next.startsWith("/") && !next.startsWith("//") ? next : "/");

const PERKS = [
  { icon: Ticket, text: "Register for any fest event in one tap" },
  { icon: QrCode, text: "One QR pass per fest, ready at the gate" },
  { icon: Users, text: "Free for students, always" },
];

/** Where someone lands after signing in when they did not arrive from a specific page. */
const HOME: Record<string, string> = { admin: "/admin", organizer: "/dashboard" };

export function AuthForm({ mode, next, expired }: { mode: "login" | "signup"; next?: string; expired?: boolean }) {
  const { user, loading, login, signup, googleSignIn } = useAuth();
  const router = useRouter();
  const [f, setF] = useState({ first_name: "", last_name: "", email: "", date_of_birth: "", password: "", confirm: "", accept_terms: false });
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{ text: string; to: string } | null>(null);
  const isSignup = mode === "signup";
  const nextQuery = next ? `?next=${encodeURIComponent(next)}` : "";
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF((x) => ({ ...x, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value }));

  // Someone who is already signed in has no use for this page
  useEffect(() => { if (!loading && user && !busy && !notice) router.replace(next ? safeNext(next) : (HOME[user.role] ?? "/")); }, [loading, user, busy, notice, router, next]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (isSignup && f.password !== f.confirm) { setError("The two passwords do not match."); return; }
    setBusy(true);
    try {
      const result = isSignup
        ? await signup({ first_name: f.first_name.trim(), last_name: f.last_name.trim(), email: f.email.trim(), date_of_birth: f.date_of_birth, password: f.password, accept_terms: f.accept_terms })
        : await login(f.email.trim(), f.password);
      router.push(next ? safeNext(next) : (HOME[result.role] ?? "/"));
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong."); setBusy(false); }
  };

  const google = async (credential: string) => {
    setBusy(true); setError("");
    try {
      const result = await googleSignIn(credential);
      const to = next ? safeNext(next) : (HOME[result.role] ?? "/");
      // Something to read first, such as the old password being switched off when Google is linked
      if (result.notice) { setNotice({ text: result.notice, to }); setBusy(false); } else router.push(to);
    } catch (err) { setError(err instanceof Error ? err.message : "Google sign-in failed."); setBusy(false); }
  };

  if (notice) {
    return (
      <div className="mx-auto flex min-h-[calc(100vh-9rem)] max-w-md flex-col justify-center gap-5 px-5">
        <Notice tone="info">{notice.text}</Notice>
        <Button size="lg" onClick={() => router.push(notice.to)}>Continue</Button>
      </div>
    );
  }

  return (
    <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-[1760px] gap-6 px-5 py-6 sm:px-8 lg:grid-cols-2">
      <motion.aside initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6 }} className="relative hidden overflow-hidden rounded-[2rem] bg-ink p-12 lg:flex lg:flex-col lg:justify-between">
        <svg className="absolute -right-16 -top-16 h-96 w-96 opacity-20" viewBox="0 0 100 115" aria-hidden><path d="M50 4 94 29v57L50 111 6 86V29z" fill="none" stroke="#f5a300" strokeWidth="2" /><path d="M50 24 76 39v37L50 91 24 76V39z" fill="none" stroke="#f5a300" strokeWidth="2" /></svg>
        <svg className="absolute -bottom-20 -left-10 h-80 w-80 opacity-20" viewBox="0 0 100 115" aria-hidden><path d="M50 4 94 29v57L50 111 6 86V29z" fill="#f5a300" /></svg>
        <p className="relative text-sm font-semibold text-brand">HiveOut</p>
        <div className="relative">
          <h2 className="font-display text-5xl font-bold leading-[1.02] tracking-[-0.02em] text-white">Your fest season starts here.</h2>
          <ul className="mt-8 space-y-4">{PERKS.map(({ icon: Icon, text }) => <li key={text} className="flex items-center gap-3 font-medium text-white"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-brand"><Icon className="h-5 w-5" /></span>{text}</li>)}</ul>
        </div>
      </motion.aside>

      <div className="flex items-center justify-center">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="w-full max-w-md py-8">
          <h1 className="font-display text-4xl font-semibold tracking-[-0.02em]">{isSignup ? "Create your account" : "Welcome back"}</h1>
          <p className="mb-8 mt-2 text-mute">{isSignup ? "One free account for every fest on HiveOut." : "Sign in to see your passes and register for events."}</p>
          <GoogleButton onCredential={google} label={isSignup ? "signup_with" : "signin_with"} />
          <div className="my-6 flex items-center gap-3 text-xs font-semibold uppercase tracking-wider text-mute"><span className="h-px flex-1 bg-black/10" />or with email<span className="h-px flex-1 bg-black/10" /></div>
          <form onSubmit={submit} className="space-y-4">
            <ErrorNote>{error}</ErrorNote>
            {error.toLowerCase().includes("admin sign-in") && <p className="text-sm"><Link href="/admin/login" className="font-semibold underline underline-offset-4">Go to the admin sign-in</Link></p>}
            {expired && !error && <Notice tone="warn">You were signed out for your security. Please sign in again.</Notice>}
            {isSignup && (
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="First name"><input className="field" required autoComplete="given-name" value={f.first_name} onChange={set("first_name")} /></Field>
                <Field label="Last name"><input className="field" required autoComplete="family-name" value={f.last_name} onChange={set("last_name")} /></Field>
              </div>
            )}
            <Field label="Email"><input className="field" type="email" required autoComplete="email" value={f.email} onChange={set("email")} placeholder="you@example.com" /></Field>
            {isSignup && <Field label="Date of birth" hint="You need to be at least 13."><input className="field" type="date" required autoComplete="bday" max={new Date(new Date().setFullYear(new Date().getFullYear() - 13)).toISOString().slice(0, 10)} min="1920-01-01" value={f.date_of_birth} onChange={set("date_of_birth")} /></Field>}
            <Field label="Password">
              <div className="relative">
                <input className="field pr-16" type={showPassword ? "text" : "password"} required minLength={isSignup ? 8 : undefined} autoComplete={isSignup ? "new-password" : "current-password"} value={f.password} onChange={set("password")} placeholder={isSignup ? "At least 8 characters" : "Your password"} />
                <button type="button" onClick={() => setShowPassword((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-sm font-semibold text-mute hover:text-ink">{showPassword ? "Hide" : "Show"}</button>
              </div>
            </Field>
            {!isSignup && <p className="-mt-2 text-right text-sm"><Link href="/forgot-password" className="font-semibold text-mute underline underline-offset-4 hover:text-ink">Forgot password?</Link></p>}
            {isSignup && <Field label="Confirm password"><input className="field" type={showPassword ? "text" : "password"} required autoComplete="new-password" value={f.confirm} onChange={set("confirm")} /></Field>}
            {isSignup && (
              <label className="flex items-start gap-3 text-sm text-neutral-700">
                <input type="checkbox" required className="mt-0.5 h-4 w-4 accent-[#111]" checked={f.accept_terms} onChange={set("accept_terms")} />
                <span>I agree to HiveOut&apos;s terms of use and privacy policy.</span>
              </label>
            )}
            <Button type="submit" size="lg" className="w-full" disabled={busy}>{busy ? "Please wait…" : isSignup ? "Create account" : "Sign in"}</Button>
          </form>
          <p className="mt-6 text-center text-sm text-mute">{isSignup ? "Already have an account? " : "New to HiveOut? "}<Link href={`${isSignup ? "/login" : "/signup"}${nextQuery}`} className="font-semibold text-ink underline underline-offset-4">{isSignup ? "Sign in" : "Create an account"}</Link></p>
        </motion.div>
      </div>
    </div>
  );
}
