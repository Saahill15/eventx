"use client";

import { useEffect, useState } from "react";

/** Live countdown to a date, ticking every second. */
export function Countdown({ to }: { to: string }) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => { setNow(Date.now()); const id = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(id); }, []);
  if (now === null) return <div className="h-16" />;
  const ms = Math.max(0, new Date(to).getTime() - now);
  const parts = [["days", Math.floor(ms / 86400000)], ["hrs", Math.floor(ms / 3600000) % 24], ["min", Math.floor(ms / 60000) % 60], ["sec", Math.floor(ms / 1000) % 60]] as const;
  return (
    <div className="flex gap-3" role="timer" aria-label="Time until the event starts">
      {parts.map(([label, v]) => (
        <div key={label} className="min-w-14 text-center">
          <div className="font-display text-4xl font-bold tabular-nums leading-none">{String(v).padStart(2, "0")}</div>
          <div className="mt-1 text-[11px] font-bold uppercase tracking-wider text-mute">{label}</div>
        </div>
      ))}
    </div>
  );
}
