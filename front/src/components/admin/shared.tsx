"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import type { AdminOverview } from "@/lib/types";

/** Headline counts, loaded once by the admin shell and shared with the sections and the sidebar badges. */
export const CountsContext = createContext<AdminOverview | null>(null);
export const useCounts = () => useContext(CountsContext);
/** Lets an action ask the shell to reload the counts, so sidebar badges stay right without changing page. */
export const RefreshCountsContext = createContext<() => void>(() => {});

/** Run an admin action, keep the error for display, and refresh afterwards. */
export function useAction(reload: () => void) {
  const refreshCounts = useContext(RefreshCountsContext);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const run = useCallback(async (fn: () => Promise<unknown>): Promise<boolean> => {
    setError(""); setBusy(true);
    let ok = true;
    try { await fn(); } catch (err) { ok = false; setError(err instanceof Error ? err.message : "That action failed."); }
    setBusy(false);
    reload();
    refreshCounts();
    return ok;
  }, [reload, refreshCounts]);
  return { run, error, setError, busy };
}

export function Stat({ label, value, hint, tone = "plain", onClick }: { label: string; value: number | string; hint?: string; tone?: "plain" | "alert"; onClick?: () => void }) {
  const body = (
    <>
      <p className="text-sm font-medium text-mute">{label}</p>
      <p className={`mt-2 font-display text-4xl font-bold tracking-tight ${tone === "alert" && Number(value) > 0 ? "text-tint-ink" : ""}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-mute">{hint}</p>}
    </>
  );
  return onClick
    ? <button onClick={onClick} className="card p-5 text-left transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)]">{body}</button>
    : <div className="card p-5">{body}</div>;
}

export function Chips<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { id: T; label: string; count?: number }[] }) {
  return (
    <div className="mb-5 flex flex-wrap gap-2" role="tablist">
      {options.map((o) => (
        <button key={o.id} role="tab" aria-selected={value === o.id} onClick={() => onChange(o.id)} className={`rounded-full px-4 py-2 text-sm font-semibold transition ${value === o.id ? "bg-ink text-white" : "bg-white text-mute shadow-[var(--shadow-card)] hover:text-ink"}`}>
          {o.label}{o.count !== undefined && o.count > 0 && <span className="ml-2 rounded-full bg-tint px-2 py-0.5 text-xs text-tint-ink">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Panel({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="card mb-5 p-6">
      <div className="mb-4 flex items-center justify-between gap-3"><h3 className="font-display text-lg font-semibold tracking-tight">{title}</h3>{action}</div>
      {children}
    </section>
  );
}

export const when = (iso: string | null | undefined) => (iso ? new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "—");

export function Detail({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className="text-xs font-semibold uppercase tracking-wider text-mute">{label}</dt><dd className="mt-0.5 break-words text-sm">{children || "—"}</dd></div>;
}
