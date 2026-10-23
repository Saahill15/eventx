"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

// `dot`, `exact`, `add`, `empty` and `loading` are small additions for this site; the rest is the standalone sidebar.
export type SidebarItem = { href: string; label: string; icon?: React.ReactNode; badge?: number; external?: boolean; dot?: "live" | "off"; exact?: boolean };
export type SidebarGroup = { id: string; label?: string; items: SidebarItem[]; add?: { href: string; label: string }; empty?: string; loading?: boolean };

/** Sidebar with folding categories. Pass `groups` (your menu) and `brand` (name or logo). */
export function Sidebar({ groups, brand = "Admin", storageKey = "sidebar:collapsed" }: {
  groups: SidebarGroup[];
  brand?: React.ReactNode;
  storageKey?: string;
}) {
  const path = usePathname();
  const [collapsed, setCollapsed] = useState<string[]>([]);

  // remember which categories are folded, per browser
  useEffect(() => {
    try {
      const saved = JSON.parse(window.localStorage.getItem(storageKey) ?? "[]");
      if (Array.isArray(saved)) setCollapsed(saved.filter((x) => typeof x === "string"));
    } catch {
      /* storage unavailable */
    }
  }, [storageKey]);

  function toggle(id: string) {
    setCollapsed((cur) => {
      const next = cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id];
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(next));
      } catch {
        /* storage unavailable */
      }
      return next;
    });
  }

  const isActive = (i: SidebarItem) => (i.exact || i.href === "/" ? path === i.href : path === i.href || path.startsWith(`${i.href}/`));

  return (
    <aside className="sb">
      <div className="sb-brand">{brand}</div>
      <nav aria-label="Main">
        {groups.map((g) => {
          const folded = !!g.label && collapsed.includes(g.id);
          return (
            <div key={g.id} className="sb-group">
              {g.label ? (
                <div className="sb-head">
                  <button type="button" className="sb-label" aria-expanded={!folded} onClick={() => toggle(g.id)}>
                    {g.label}
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
                  </button>
                  {g.add ? <Link href={g.add.href} className="sb-add" aria-label={g.add.label} title={g.add.label}>+</Link> : null}
                </div>
              ) : null}
              {!folded ? (
                <div className="sb-items">
                  {g.loading ? <p className="sb-empty">Loading…</p> : g.items.length === 0 && g.empty ? <p className="sb-empty">{g.empty}</p> : null}
                  {g.items.map((i) => (
                    <Link
                      key={i.href}
                      href={i.href}
                      aria-current={!i.external && isActive(i) ? "page" : undefined}
                      {...(i.external ? { target: "_blank", rel: "noopener" } : {})}
                    >
                      {i.dot ? <span className={`sb-dot ${i.dot}`} aria-hidden="true" /> : i.icon}
                      <span className="sb-text">{i.label}</span>
                      {i.badge ? <b className="sb-badge">{i.badge}</b> : null}
                    </Link>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
