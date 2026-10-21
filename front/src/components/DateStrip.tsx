"use client";

import Link from "next/link";
import { motion } from "motion/react";

const key = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** The next two weeks as tappable days, like a cinema date picker. Links when no handler is given. */
export function DateStrip({ value, onSelect, days = 14 }: { value?: string | null; onSelect?: (v: string | null) => void; days?: number }) {
  const today = new Date();
  const list = Array.from({ length: days }, (_, i) => { const d = new Date(today); d.setDate(today.getDate() + i); return d; });
  return (
    <div className="no-scrollbar -mx-5 flex gap-2 overflow-x-auto px-5 py-1 sm:-mx-8 sm:px-8" role="group" aria-label="Pick a day">
      {list.map((d, i) => {
        const k = key(d);
        const on = value === k;
        const inner = (
          <>
            {on && <motion.span layoutId="date-pill" className="absolute inset-0 rounded-2xl bg-ink" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
            <span className={`relative text-[11px] font-bold uppercase tracking-wider ${on ? "text-white/70" : "text-mute"}`}>{i === 0 ? "Today" : d.toLocaleDateString("en-IN", { weekday: "short" })}</span>
            <span className={`relative font-display text-2xl font-bold leading-none ${on ? "text-white" : ""}`}>{d.getDate()}</span>
            <span className={`relative text-[11px] font-medium ${on ? "text-white/70" : "text-mute"}`}>{d.toLocaleDateString("en-IN", { month: "short" })}</span>
          </>
        );
        const cls = "relative flex h-[5.25rem] w-[4.25rem] shrink-0 flex-col items-center justify-center gap-0.5 rounded-2xl bg-wash transition hover:bg-neutral-200";
        return onSelect ? (
          <button key={k} onClick={() => onSelect(on ? null : k)} aria-pressed={on} className={cls}>{inner}</button>
        ) : (
          <Link key={k} href={`/events?date=${k}`} className={cls}>{inner}</Link>
        );
      })}
    </div>
  );
}
