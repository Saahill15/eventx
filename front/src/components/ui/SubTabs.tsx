"use client";

import type { ReactNode } from "react";

export interface SubTabItem<T extends string> { id: T; label: string; badge?: number; tour?: string }

/**
 * The row of sections inside a page (Finance's Spending and Budget, the competition's Standings and Auction...). One look everywhere:
 * underlined text under the page's main areas, so it never reads as a second set of main buttons.
 */
export function SubTabs<T extends string>({ label, items, value, onChange, children }: { label: string; items: SubTabItem<T>[]; value: T; onChange: (id: T) => void; children?: ReactNode }) {
  return (
    <nav role="tablist" aria-label={label} className="no-scrollbar -mx-1 flex gap-1 overflow-x-auto border-b border-black/10 px-1">
      {items.map((t) => (
        <button key={t.id} role="tab" data-tour={t.tour} aria-selected={value === t.id} onClick={() => onChange(t.id)} className={`-mb-px shrink-0 border-b-2 px-4 py-2.5 text-sm font-semibold transition ${value === t.id ? "border-ink text-ink" : "border-transparent text-mute hover:text-ink"}`}>
          {t.label}{!!t.badge && t.badge > 0 && <span className="ml-2 rounded-full bg-brand px-2 py-0.5 text-xs text-on-brand">{t.badge}</span>}
        </button>
      ))}
      {children}
    </nav>
  );
}
