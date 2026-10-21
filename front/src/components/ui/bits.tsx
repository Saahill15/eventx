import type { ReactNode } from "react";

export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "red" | "green" | "amber" }) {
  const tones = {
    neutral: "bg-black/5 text-neutral-700",
    red: "bg-hive-50 text-hive-ink",
    green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
  };
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${tones[tone]}`}>{children}</span>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-2xl bg-black/[0.06] ${className}`} />;
}

export function EmptyState({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="glass rounded-3xl px-6 py-14 text-center">
      <p className="font-display text-xl font-bold tracking-tight">{title}</p>
      {body && <p className="mx-auto mt-2 max-w-md text-neutral-500">{body}</p>}
      {action && <div className="mt-6 flex justify-center">{action}</div>}
    </div>
  );
}

export function SectionHeading({ eyebrow, title, action }: { eyebrow?: string; title: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex items-end justify-between gap-4">
      <div>
        {eyebrow && <p className="mb-1 text-xs font-bold uppercase tracking-[0.14em] text-hive-ink">{eyebrow}</p>}
        <h2 className="font-display text-2xl font-extrabold tracking-tight sm:text-3xl">{title}</h2>
      </div>
      {action}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  if (!children) return null;
  return <div role="alert" className="rounded-2xl border border-red-100 bg-red-50/80 px-4 py-3 text-sm text-red-700">{children}</div>;
}
