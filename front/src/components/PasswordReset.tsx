"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { MailCheck } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "./ui/Button";
import { ErrorNote, Field, Notice } from "./ui/bits";

function Shell({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto flex min-h-[calc(100vh-9rem)] max-w-md items-center px-5">
      <div className="card w-full space-y-5 p-8">
        <div><h1 className="font-display text-3xl font-semibold tracking-tight">{title}</h1>{sub && <p className="mt-2 text-sm text-mute">{sub}</p>}</div>
        {children}
      </div>
    </div>
  );
}

/** Ask for a link to choose a new password. The answer never says whether the email has an account. */
export function ForgotPassword({ admin }: { admin: boolean }) {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState<{ message: string; dev_link: string | null } | null>(null);
  const back = admin ? "/admin/login" : "/login";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try { setSent(await api("/api/auth/password/forgot", { method: "POST", body: { email: email.trim() } })); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not send the link."); }
    setBusy(false);
  };

  if (sent) {
    return (
      <Shell title="Check your email">
        <div className="flex items-start gap-3 rounded-2xl bg-wash p-4 text-sm"><MailCheck className="mt-0.5 h-5 w-5 shrink-0" /><p>{sent.message}</p></div>
        {sent.dev_link && (
          <Notice tone="warn">
            <strong>Development only.</strong> Email is not connected yet, so here is the link that would have been sent:{" "}
            <a href={sent.dev_link} className="break-all font-semibold underline underline-offset-2">{sent.dev_link}</a>
          </Notice>
        )}
        <Button href={back} variant="outline" className="w-full">Back to sign in</Button>
      </Shell>
    );
  }

  return (
    <Shell title="Forgot your password?" sub="Enter the email you sign in with and we will send you a link to choose a new one.">
      <form onSubmit={submit} className="space-y-4">
        <ErrorNote>{error}</ErrorNote>
        <Field label="Email"><input className="field" type="email" required autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Button type="submit" size="lg" className="w-full" disabled={busy}>{busy ? "Sending…" : "Send me a link"}</Button>
      </form>
      <p className="text-center text-sm"><Link href={back} className="font-semibold text-mute underline underline-offset-4 hover:text-ink">Back to sign in</Link></p>
    </Shell>
  );
}

/** Choose a new password from the link. Every device signed in with the old one is signed out. */
export function ResetPassword({ token }: { token: string }) {
  const [valid, setValid] = useState<boolean | null>(token ? null : false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<{ admin: boolean } | null>(null);

  useEffect(() => {
    if (!token) return;
    api<{ valid: boolean }>(`/api/auth/password/reset/check?token=${encodeURIComponent(token)}`).then((r) => setValid(r.valid)).catch(() => setValid(false));
  }, [token]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirm) { setError("The two passwords do not match."); return; }
    setBusy(true);
    try { setDone(await api<{ admin: boolean }>("/api/auth/password/reset", { method: "POST", body: { token, new_password: password } })); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not change the password."); }
    setBusy(false);
  };

  if (done) {
    return (
      <Shell title="Password changed" sub="You have been signed out everywhere. Sign in with your new password.">
        <Button href={done.admin ? "/admin/login" : "/login"} size="lg" className="w-full">Sign in</Button>
      </Shell>
    );
  }
  if (valid === null) return <Shell title="Checking your link…">{null}</Shell>;
  if (!valid) {
    return (
      <Shell title="This link has expired" sub="Reset links work once, for 30 minutes, and only the newest one works.">
        <Button href="/forgot-password" size="lg" className="w-full">Send me a new link</Button>
      </Shell>
    );
  }
  return (
    <Shell title="Choose a new password">
      <form onSubmit={submit} className="space-y-4">
        <ErrorNote>{error}</ErrorNote>
        <Field label="New password">
          <div className="relative">
            <input className="field pr-16" type={show ? "text" : "password"} required minLength={8} autoComplete="new-password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" />
            <button type="button" onClick={() => setShow((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-sm font-semibold text-mute hover:text-ink">{show ? "Hide" : "Show"}</button>
          </div>
        </Field>
        <Field label="Confirm new password"><input className="field" type={show ? "text" : "password"} required autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></Field>
        <Button type="submit" size="lg" className="w-full" disabled={busy}>{busy ? "Saving…" : "Save new password"}</Button>
      </form>
    </Shell>
  );
}
