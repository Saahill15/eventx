import type { ReactNode } from "react";

const tones = {
  neutral: "bg-wash text-neutral-700",
  amber: "bg-tint text-tint-ink",
  green: "bg-mint text-emerald-800",
  red: "bg-red-100 text-red-700",
  lilac: "bg-lilac text-violet-800",
} as const;

export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: keyof typeof tones }) {
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${tones[tone]}`}>{children}</span>;
}

/** Pale-blue label with a leading icon, as used under hero headings and on cards. */
export function InfoChip({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return <span className="inline-flex items-center gap-2 rounded-full bg-chip px-4 py-2 text-sm font-medium text-chip-ink">{icon}{children}</span>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-2xl bg-black/[0.06] ${className}`} />;
}

export function EmptyState({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="card px-6 py-16 text-center">
      <p className="font-display text-2xl font-bold tracking-tight">{title}</p>
      {body && <p className="mx-auto mt-2 max-w-md text-mute">{body}</p>}
      {action && <div className="mt-6 flex justify-center">{action}</div>}
    </div>
  );
}

export function SectionHead({ kicker, title, action }: { kicker?: string; title: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex items-end justify-between gap-4">
      <div>
        {kicker && <p className="mb-2 text-sm font-semibold text-chip-ink">{kicker}</p>}
        <h2 className="font-display text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">{title}</h2>
      </div>
      {action}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  if (!children) return null;
  return <div role="alert" className="rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">{children}</div>;
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn" | "ok"; children: ReactNode }) {
  const t = { info: "bg-wash text-neutral-700", warn: "bg-chip text-chip-ink", ok: "bg-mint text-emerald-800" };
  return <div className={`rounded-2xl px-4 py-3 text-sm ${t[tone]}`}>{children}</div>;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold">{label}</span>
      {children}
      {hint && <span className="mt-1.5 block text-xs text-mute">{hint}</span>}
    </label>
  );
}
