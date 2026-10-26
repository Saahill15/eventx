"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { College, StudentStatus } from "@/lib/types";
import { Button } from "./ui/Button";
import { ErrorNote, Field, Notice, Pill, Skeleton } from "./ui/bits";

/** Verify as a student with a college email and a six-digit code. Needed to join a fest team or book student prices. */
export function StudentVerification() {
  const [status, setStatus] = useState<StudentStatus | null>(null);
  const [colleges, setColleges] = useState<College[]>([]);
  const [email, setEmail] = useState("");
  const [collegeId, setCollegeId] = useState<number | "">("");
  const [needCollege, setNeedCollege] = useState(false);
  const [code, setCode] = useState("");
  const [sentTo, setSentTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(() => {
    api<StudentStatus>("/api/users/me/student").then(setStatus).catch((e) => setError(e instanceof Error ? e.message : "Could not load your student status."));
  }, []);
  useEffect(() => {
    load();
    api<College[]>("/api/colleges/").then(setColleges).catch(() => {});
  }, [load]);

  const sendCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      await api("/api/users/me/student/email", { method: "POST", body: { email: email.trim(), college_id: collegeId === "" ? null : collegeId } });
      setSentTo(email.trim()); setNeedCollege(false); setNotice("We sent a code to your college email. It works for 15 minutes.");
      load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not send the code.";
      // Our list has no match for this domain, so the person picks their college
      if (message.startsWith("Choose your college")) setNeedCollege(true);
      setError(message);
    }
    setBusy(false);
  };

  const confirmCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      const next = await api<StudentStatus>("/api/users/me/student/email/confirm", { method: "POST", body: { code: code.trim() } });
      setStatus(next); setCode(""); setSentTo("");
      setNotice("You are verified as a student.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "That code did not work.");
    }
    setBusy(false);
  };

  if (!status) return <div className="card p-7" id="student"><Skeleton className="h-24" /></div>;

  const until = status.verified_until ? new Date(status.verified_until).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : null;

  return (
    <section id="student" className="card space-y-4 p-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-xl font-semibold tracking-tight">Student status</h2>
        {status.verified ? <Pill tone="green">Verified until {until}</Pill> : <Pill tone="amber">Not verified</Pill>}
      </div>
      <p className="text-sm text-mute">Verified students can join fest teams and book student prices. Use your college email; the code proves you can read it.</p>
      <ErrorNote>{error}</ErrorNote>
      {notice && <Notice tone="ok">{notice}</Notice>}
      {status.last_rejection && !status.verified && <Notice tone="warn">Your last check was not approved: {status.last_rejection}</Notice>}

      {status.verified && !status.can_verify && <p className="text-sm text-mute">You can renew your verification in the last few weeks before it ends.</p>}

      {status.can_verify && (sentTo || status.pending?.method === "email") ? (
        <form onSubmit={confirmCode} className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
          <Field label="6-digit code" hint={`Sent to ${sentTo || status.pending?.email || "your college email"}`}>
            <input className="field" inputMode="numeric" autoComplete="one-time-code" maxLength={6} required value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} placeholder="123456" />
          </Field>
          <div className="flex gap-2">
            <Button type="submit" disabled={busy || code.length !== 6}>{busy ? "Checking…" : "Confirm"}</Button>
            <Button type="button" variant="outline" disabled={busy} onClick={() => { setSentTo(""); setCode(""); }}>Use another email</Button>
          </div>
        </form>
      ) : status.can_verify ? (
        <form onSubmit={sendCode} className="grid gap-4 sm:grid-cols-2 sm:items-end">
          <Field label="College email" hint="For example name@college.edu">
            <input className="field" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@college.edu" />
          </Field>
          {needCollege && (
            <Field label="Your college" hint="Pick the college this email belongs to">
              <select className="field" required value={collegeId} onChange={(e) => setCollegeId(e.target.value ? Number(e.target.value) : "")}>
                <option value="">Choose a college</option>
                {colleges.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </Field>
          )}
          <div><Button type="submit" disabled={busy || !email.trim()}>{busy ? "Sending…" : "Send code"}</Button></div>
        </form>
      ) : null}
    </section>
  );
}
