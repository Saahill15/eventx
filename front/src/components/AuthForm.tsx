"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { QrCode, Ticket, Users } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { College } from "@/lib/types";
import { Button } from "./ui/Button";
import { ErrorNote, Field, Notice } from "./ui/bits";

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
  const { user, loading, login, signup } = useAuth();
  const router = useRouter();
  const [f, setF] = useState({ first_name: "", last_name: "", email: "", phone: "", password: "", confirm: "", college_id: "", study_year: "", accept_terms: false });
  const [colleges, setColleges] = useState<College[]>([]);
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const isSignup = mode === "signup";
  const nextQuery = next ? `?next=${encodeURIComponent(next)}` : "";
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF((x) => ({ ...x, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value }));

  // Someone who is already signed in has no use for this page
  useEffect(() => { if (!loading && user && !busy) router.replace(next ? safeNext(next) : (HOME[user.role] ?? "/")); }, [loading, user, busy, router, next]);
  useEffect(() => { if (isSignup) api<College[]>("/api/colleges/").then(setColleges).catch(() => {}); }, [isSignup]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (isSignup && f.password !== f.confirm) { setError("The two passwords do not match."); return; }
    setBusy(true);
    try {
      const result = isSignup
        ? await signup({ first_name: f.first_name.trim(), last_name: f.last_name.trim(), email: f.email.trim(), phone: f.phone.trim(), password: f.password, college_id: f.college_id ? Number(f.college_id) : null, study_year: f.college_id && f.study_year ? Number(f.study_year) : null, accept_terms: f.accept_terms })
        : await login(f.email.trim(), f.password);
      router.push(next ? safeNext(next) : (HOME[result.role] ?? "/"));
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong."); setBusy(false); }
  };

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
            <Field label="Email"><input className="field" type="email" required autoComplete="email" value={f.email} onChange={set("email")} placeholder="you@college.edu" /></Field>
            {isSignup && <Field label="Mobile number" hint="Organisers may call you about an event you registered for."><input className="field" type="tel" required autoComplete="tel" pattern="^\+?[0-9 ()\-]{7,20}$" title="Digits only, with an optional + at the start" value={f.phone} onChange={set("phone")} placeholder="+91 98765 43210" /></Field>}
            {isSignup && (
              <div className="grid gap-4 sm:grid-cols-[1fr_9rem]">
                <Field label="College" hint="Optional. Needed later to get student prices.">
                  <select className="field" value={f.college_id} onChange={set("college_id")}><option value="">I am not a student</option>{colleges.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
                </Field>
                <Field label="Year"><select className="field" value={f.study_year} onChange={set("study_year")} disabled={!f.college_id}><option value="">–</option>{[1, 2, 3, 4, 5].map((y) => <option key={y} value={y}>Year {y}</option>)}</select></Field>
              </div>
            )}
            <Field label="Password">
              <div className="relative">
                <input className="field pr-16" type={showPassword ? "text" : "password"} required minLength={isSignup ? 8 : undefined} autoComplete={isSignup ? "new-password" : "current-password"} value={f.password} onChange={set("password")} placeholder={isSignup ? "At least 8 characters" : "Your password"} />
                <button type="button" onClick={() => setShowPassword((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-sm font-semibold text-mute hover:text-ink">{showPassword ? "Hide" : "Show"}</button>
              </div>
            </Field>
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
