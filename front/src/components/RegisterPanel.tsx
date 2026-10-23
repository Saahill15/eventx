"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Clock, Copy, Ticket, Users, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { CityPass, FestEvent, FestPass, Question, Registration, Team } from "@/lib/types";
import { Button } from "./ui/Button";
import { ErrorNote, Field } from "./ui/bits";

type State = "unknown" | "none" | "confirmed" | "waiting" | "rejected";
type Answers = Record<number, string>;

/** The event's own questions (team name, T-shirt size...). Shown before registering, joining or starting a team. */
function QuestionFields({ questions, answers, onChange }: { questions: Question[]; answers: Answers; onChange: (a: Answers) => void }) {
  if (questions.length === 0) return null;
  const set = (id: number, v: string) => onChange({ ...answers, [id]: v });
  return (
    <div className="space-y-3">
      {questions.map((q) => (
        <Field key={q.id} label={`${q.label}${q.required ? "" : " (optional)"}`}>
          {q.kind === "short_text" ? (
            <input className="field" required={q.required} maxLength={300} value={answers[q.id] ?? ""} onChange={(e) => set(q.id, e.target.value)} />
          ) : (
            <select className="field" required={q.required} value={answers[q.id] ?? ""} onChange={(e) => set(q.id, e.target.value)}>
              <option value="">Choose</option>
              {(q.kind === "yes_no" ? ["yes", "no"] : q.options ?? []).map((o) => <option key={o} value={o}>{q.kind === "yes_no" ? (o === "yes" ? "Yes" : "No") : o}</option>)}
            </select>
          )}
        </Field>
      ))}
    </div>
  );
}

const toAnswers = (a: Answers) => Object.entries(a).filter(([, v]) => v.trim()).map(([id, value]) => ({ question_id: Number(id), value }));

function TeamCard({ team, onLeave, busy }: { team: Team; onLeave: () => void; busy: boolean }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => { try { await navigator.clipboard.writeText(team.code ?? ""); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* blocked */ } };
  const status = team.status === "approved" ? "Confirmed" : team.status === "pending" ? "Waiting for the organisers" : "Not approved";
  return (
    <div className="space-y-4 rounded-2xl bg-wash p-4">
      <div className="flex items-start justify-between gap-3">
        <div><p className="flex items-center gap-2 font-semibold"><Users className="h-4 w-4" />{team.name}</p><p className="text-xs text-mute">{status}</p></div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${team.complete ? "bg-mint text-emerald-800" : "bg-tint text-tint-ink"}`}>{team.size}/{team.team_max} {team.complete ? "" : `· needs ${(team.team_min ?? 1) - team.size} more`}</span>
      </div>
      {team.code && team.status !== "rejected" && (
        <div>
          <p className="text-xs font-semibold text-mute">Team code: share it with your teammates</p>
          <div className="mt-1 flex items-center gap-2"><code className="rounded-xl bg-white px-3 py-2 font-mono text-lg font-bold tracking-[0.2em]">{team.code}</code><Button size="sm" variant="outline" onClick={copy}><Copy className="h-4 w-4" />{copied ? "Copied" : "Copy"}</Button></div>
        </div>
      )}
      <ul className="space-y-1 text-sm">{team.members.map((m) => <li key={m.registration_id}>{m.name}{m.is_leader && <span className="ml-2 text-xs font-semibold text-tint-ink">Leader</span>}</li>)}</ul>
      <button disabled={busy} onClick={onLeave} className="text-sm font-semibold text-red-600 hover:underline">{team.i_am_leader ? "Break up the team" : "Leave the team"}</button>
      <Link href="/my-passes" className="block text-sm font-semibold underline underline-offset-4">Open my passes</Link>
    </div>
  );
}

export function RegisterPanel({ event, hasEnded }: { event: FestEvent; hasEnded: boolean }) {
  const { user, loading } = useAuth();
  const [state, setState] = useState<State>("unknown");
  const [hasFestPass, setHasFestPass] = useState(false);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Answers>({});
  const [team, setTeam] = useState<Team | null>(null);
  const [teamMode, setTeamMode] = useState<"" | "create" | "join">("");
  const [teamName, setTeamName] = useState("");
  const [code, setCode] = useState("");
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const isFest = event.event_type === "fest";
  const needsRegistration = isFest && event.requires_registration;
  const isTeam = needsRegistration && event.is_team_event;
  const next = encodeURIComponent(`/events/${event.id}`);

  const refresh = useCallback(async () => {
    try {
      if (isTeam) {
        const t = await api<Team>(`/api/fest-events/${event.id}/my-team`).catch(() => null);
        setTeam(t);
        setState(t ? (t.status === "approved" ? "confirmed" : t.status === "pending" ? "waiting" : "rejected") : "none");
      } else if (needsRegistration) {
        const regs = await api<Registration[]>("/api/fest-events/my-registrations");
        const mine = regs.find((r) => r.event_id === event.id);
        setState(!mine ? "none" : mine.approval_status === "approved" ? "confirmed" : mine.approval_status === "pending" ? "waiting" : "rejected");
      } else if (isFest) {
        await api<FestPass>(`/api/fests/${event.fest_slug}/my-pass`).then(() => setHasFestPass(true)).catch(() => setHasFestPass(false));
        setState("none");
      } else {
        const passes = await api<CityPass[]>("/api/passes/my");
        setState(passes.some((p) => p.event_id === event.id) ? "confirmed" : "none");
      }
    } catch { setState("none"); }
  }, [event.id, event.fest_slug, isFest, needsRegistration, isTeam]);

  useEffect(() => { if (user) refresh(); }, [user, refresh]);
  useEffect(() => { if (needsRegistration) api<Question[]>(`/api/events/${event.id}/questions`).then(setQuestions).catch(() => {}); }, [event.id, needsRegistration]);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); setAsking(false); setTeamMode(""); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  };
  const getPass = () => api(`/api/fests/${event.fest_slug}/entry-pass`, { method: "POST" });

  const register = () => {
    // With questions, the first click shows them; the second sends the answers
    if (needsRegistration && questions.length > 0 && !asking) { setAsking(true); return; }
    run(async () => {
      if (needsRegistration) { await getPass(); await api(`/api/fest-events/${event.id}/register`, { method: "POST", body: { answers: toAnswers(answers) } }); }
      else if (isFest) await getPass();
      else await api(`/api/passes/${event.id}/register`, { method: "POST" });
    });
  };
  const createTeam = (e: React.FormEvent) => { e.preventDefault(); run(async () => { await getPass(); await api(`/api/fest-events/${event.id}/teams`, { method: "POST", body: { name: teamName.trim(), answers: toAnswers(answers) } }); }); };
  const joinTeam = (e: React.FormEvent) => { e.preventDefault(); run(async () => { await getPass(); await api("/api/fest-events/teams/join", { method: "POST", body: { code: code.trim(), answers: toAnswers(answers) } }); }); };
  const leave = () => {
    const msg = isTeam && team?.i_am_leader ? "Break up the team? Everyone in it loses their registration." : "Cancel your registration?";
    if (window.confirm(msg)) run(() => api(`/api/fest-events/${event.id}/register`, { method: "DELETE" }));
  };

  if (hasEnded) return <p className="rounded-2xl bg-wash px-4 py-4 text-center text-sm font-semibold text-mute">This event has already taken place.</p>;
  if (event.cancelled) return <p className="rounded-2xl bg-red-50 px-4 py-4 text-center text-sm font-semibold text-red-700">This event has been cancelled.</p>;
  if (loading) return <div className="h-14 animate-pulse rounded-full bg-wash" />;

  if (!user) {
    return (
      <div className="space-y-3">
        <Button href={`/login?next=${next}`} size="lg" className="w-full">Sign in to {needsRegistration || !isFest ? "register" : "get your pass"}</Button>
        <p className="text-center text-sm text-mute">New here? <Link href={`/signup?next=${next}`} className="font-semibold text-ink underline underline-offset-4">Create a free account</Link></p>
      </div>
    );
  }

  if (isTeam && team) return <div className="space-y-3"><ErrorNote>{error}</ErrorNote><TeamCard team={team} busy={busy} onLeave={leave} /></div>;

  const done = (icon: React.ReactNode, title: string, body?: string, cancellable = false) => (
    <motion.div initial={{ opacity: 0, scale: 0.94 }} animate={{ opacity: 1, scale: 1 }} transition={{ type: "spring", stiffness: 300, damping: 20 }} className="rounded-2xl bg-wash p-4">
      <p className="flex items-center gap-2 font-semibold"><motion.span initial={{ scale: 0, rotate: -30 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: "spring", stiffness: 400, damping: 14, delay: 0.1 }} className="inline-flex">{icon}</motion.span>{title}</p>
      {body && <p className="mt-1 text-sm text-mute">{body}</p>}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm font-semibold">
        <Link href="/my-passes" className="underline underline-offset-4">Open my passes</Link>
        {cancellable && <button disabled={busy} onClick={leave} className="text-red-600 hover:underline">Cancel registration</button>}
      </div>
    </motion.div>
  );

  if (state === "confirmed") return done(<CheckCircle2 className="h-5 w-5 text-emerald-600" />, "You are registered", undefined, needsRegistration);
  if (state === "waiting") return done(<Clock className="h-5 w-5 text-chip-ink" />, "Request sent", "The organisers will confirm your spot. It will show here once approved.", needsRegistration);
  if (state === "rejected") return done(<XCircle className="h-5 w-5 text-red-600" />, "Not approved", "The organisers could not confirm this registration.");
  if (isFest && !needsRegistration && hasFestPass) return done(<Ticket className="h-5 w-5 text-chip-ink" />, "Entry included", "No registration needed. Your fest pass gets you in.");

  if (isTeam) {
    return (
      <div className="space-y-4">
        <ErrorNote>{error}</ErrorNote>
        <p className="text-sm text-mute">A team event for teams of {event.team_min}–{event.team_max}. One person starts the team and shares its code; the others join with it.</p>
        {teamMode === "" && (
          <div className="grid gap-2">
            <Button size="lg" onClick={() => setTeamMode("create")} disabled={state === "unknown"}>Start a team</Button>
            <Button size="lg" variant="outline" onClick={() => setTeamMode("join")} disabled={state === "unknown"}>Join with a code</Button>
          </div>
        )}
        {teamMode === "create" && (
          <form onSubmit={createTeam} className="space-y-3">
            <Field label="Team name"><input className="field" required maxLength={80} autoFocus value={teamName} onChange={(e) => setTeamName(e.target.value)} /></Field>
            <QuestionFields questions={questions} answers={answers} onChange={setAnswers} />
            <div className="flex gap-2"><Button type="submit" disabled={busy}>{busy ? "Please wait…" : "Start the team"}</Button><Button type="button" variant="ghost" onClick={() => setTeamMode("")}>Back</Button></div>
          </form>
        )}
        {teamMode === "join" && (
          <form onSubmit={joinTeam} className="space-y-3">
            <Field label="Team code"><input className="field font-mono uppercase tracking-[0.2em]" required maxLength={12} autoFocus value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="ABC234" /></Field>
            <QuestionFields questions={questions} answers={answers} onChange={setAnswers} />
            <div className="flex gap-2"><Button type="submit" disabled={busy}>{busy ? "Please wait…" : "Join the team"}</Button><Button type="button" variant="ghost" onClick={() => setTeamMode("")}>Back</Button></div>
          </form>
        )}
        {event.approval_mode === "manual" && <p className="text-center text-xs text-mute">The organisers approve each team.</p>}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <ErrorNote>{error}</ErrorNote>
      {asking && <QuestionFields questions={questions} answers={answers} onChange={setAnswers} />}
      <Button onClick={register} disabled={busy || state === "unknown"} size="lg" className="w-full">{busy ? "Please wait…" : asking ? "Send registration" : needsRegistration ? "Register" : isFest ? "Get free fest pass" : "Register"}</Button>
      {asking && <button onClick={() => setAsking(false)} className="w-full text-center text-sm font-semibold text-mute hover:text-ink">Back</button>}
      {isFest && !needsRegistration && <p className="text-center text-xs text-mute">No registration needed. The free fest pass covers entry.</p>}
      {needsRegistration && event.approval_mode === "manual" && <p className="text-center text-xs text-mute">The organisers approve each registration.</p>}
      {!event.is_free && event.price > 0 && <p className="text-center text-xs text-mute">Online payment is not available yet. The organisers will tell you how to pay.</p>}
    </div>
  );
}
