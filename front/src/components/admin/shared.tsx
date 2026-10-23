"use client";

import Link from "next/link";
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
      <p className="text-[13px] text-mute">{label}</p>
      <p className={`mt-1 text-[28px] font-semibold leading-none tracking-tight ${tone === "alert" && Number(value) > 0 ? "text-[var(--ws-accent)]" : ""}`}>{value}</p>
      {hint && <p className="mt-1.5 text-[13px] text-mute">{hint}</p>}
    </>
  );
  return onClick
    ? <button onClick={onClick} className="card p-5 text-left transition hover:bg-black/[0.015]">{body}</button>
    : <div className="card p-5">{body}</div>;
}

/** Several numbers in one card, split into cells. */
export function StatStrip({ items }: { items: { label: string; value: number | string; hint?: string; alert?: boolean; href?: string }[] }) {
  return (
    <div className="card grid grid-cols-2 overflow-hidden lg:grid-cols-4">
      {items.map((s, n) => {
        const body = (
          <>
            <p className="text-[13px] text-mute">{s.label}</p>
            <p className={`mt-1.5 text-[28px] font-semibold leading-none tracking-tight ${s.alert && Number(s.value) > 0 ? "text-[var(--ws-accent)]" : ""}`}>{s.value}</p>
            <p className="mt-2 min-h-[1.25rem] text-[13px] text-mute">{s.hint}</p>
          </>
        );
        const cell = `border-[var(--ws-border)] p-5 ${n % 2 === 1 ? "border-l" : ""} ${n >= 2 ? "border-t lg:border-t-0" : ""} ${n > 0 ? "lg:border-l" : ""}`;
        return s.href ? <Link key={s.label} href={s.href} className={`${cell} block transition hover:bg-black/[0.015]`}>{body}</Link> : <div key={s.label} className={cell}>{body}</div>;
      })}
    </div>
  );
}

/** A white card with a title row (and an optional link on the right) and a body. */
export function ListCard({ title, count, href, linkLabel = "View all", children }: { title: string; count?: number; href?: string; linkLabel?: string; children: ReactNode }) {
  return (
    <section className="card overflow-hidden">
      <div className="flex h-12 items-center justify-between border-b border-[var(--ws-border)] px-5">
        <h2 className="text-[14px] font-semibold">{title}{count !== undefined && <span className="ml-2 font-normal text-mute">{count}</span>}</h2>
        {href && <Link href={href} className="text-[13px] text-mute hover:text-ink">{linkLabel}</Link>}
      </div>
      {children}
    </section>
  );
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
