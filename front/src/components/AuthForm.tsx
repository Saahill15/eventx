"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { useState } from "react";
import { QrCode, Ticket, Users } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Button } from "./ui/Button";
import { ErrorNote, Field } from "./ui/bits";

/** Only follow same-site paths after signing in, so a crafted link cannot send people elsewhere. */
const safeNext = (next: string | undefined) => (next && next.startsWith("/") && !next.startsWith("//") ? next : "/");

const PERKS = [
  { icon: Ticket, text: "Register for any fest event in one tap" },
  { icon: QrCode, text: "One QR pass per fest, ready at the gate" },
  { icon: Users, text: "Free for students, always" },
];

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
      if (isSignup) await signup(name.trim(), email.trim(), password); else await login(email.trim(), password);
      router.push(safeNext(next));
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong."); setBusy(false); }
  };

  return (
    <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-7xl gap-6 px-5 py-6 sm:px-8 lg:grid-cols-2">
      <motion.aside initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6 }} className="relative hidden overflow-hidden rounded-[2rem] bg-gradient-to-br from-amber via-amber-300 to-orange-300 p-12 lg:flex lg:flex-col lg:justify-between">
        <svg className="absolute -right-16 -top-16 h-96 w-96 opacity-25" viewBox="0 0 100 115" aria-hidden><path d="M50 4 94 29v57L50 111 6 86V29z" fill="none" stroke="#fff" strokeWidth="2" /><path d="M50 24 76 39v37L50 91 24 76V39z" fill="none" stroke="#fff" strokeWidth="2" /></svg>
        <svg className="absolute -bottom-20 -left-10 h-80 w-80 opacity-20" viewBox="0 0 100 115" aria-hidden><path d="M50 4 94 29v57L50 111 6 86V29z" fill="#fff" /></svg>
        <p className="relative text-xs font-bold uppercase tracking-[0.18em] text-amber-ink">HiveOut</p>
        <div className="relative">
          <h2 className="font-display text-5xl font-bold leading-[1.02] tracking-[-0.02em] text-ink">Your fest season starts here.</h2>
          <ul className="mt-8 space-y-4">{PERKS.map(({ icon: Icon, text }) => <li key={text} className="flex items-center gap-3 font-semibold text-ink"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/70"><Icon className="h-5 w-5" /></span>{text}</li>)}</ul>
        </div>
      </motion.aside>

      <div className="flex items-center justify-center">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="w-full max-w-md py-8">
          <h1 className="font-display text-4xl font-bold tracking-[-0.02em]">{isSignup ? "Create your account" : "Welcome back"}</h1>
          <p className="mb-8 mt-2 text-mute">{isSignup ? "One free account for every fest on HiveOut." : "Sign in to see your passes and register for events."}</p>
          <form onSubmit={submit} className="space-y-4">
            <ErrorNote>{error}</ErrorNote>
            {isSignup && <Field label="Full name"><input className="field" required autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" /></Field>}
            <Field label="Email"><input className="field" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@college.edu" /></Field>
            <Field label="Password"><input className="field" type="password" required minLength={isSignup ? 8 : undefined} autoComplete={isSignup ? "new-password" : "current-password"} value={password} onChange={(e) => setPassword(e.target.value)} placeholder={isSignup ? "At least 8 characters" : "Your password"} /></Field>
            <Button type="submit" size="lg" className="w-full" disabled={busy}>{busy ? "Please wait…" : isSignup ? "Create account" : "Sign in"}</Button>
          </form>
          <p className="mt-6 text-center text-sm text-mute">{isSignup ? "Already have an account? " : "New to HiveOut? "}<Link href={`${isSignup ? "/login" : "/signup"}${nextQuery}`} className="font-semibold text-ink underline underline-offset-4">{isSignup ? "Sign in" : "Create an account"}</Link></p>
        </motion.div>
      </div>
    </div>
  );
}
