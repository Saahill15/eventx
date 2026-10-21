import type { ReactNode } from "react";

/** A ticket-shaped card: a coloured head, a perforated edge with side notches, and a body. */
export function TicketShell({ head, children, tint = "bg-chip" }: { head: ReactNode; children: ReactNode; tint?: string }) {
  return (
    <div className="relative overflow-hidden rounded-3xl bg-white shadow-[var(--shadow-card)]">
      <div className={`${tint} px-6 pb-7 pt-6`}>{head}</div>
      <div className="relative">
        <div className="border-t-2 border-dashed border-black/10" />
        <span className="absolute -left-3 -top-3 h-6 w-6 rounded-full bg-fog" />
        <span className="absolute -right-3 -top-3 h-6 w-6 rounded-full bg-fog" />
      </div>
      <div className="px-6 pb-6 pt-6">{children}</div>
    </div>
  );
}
