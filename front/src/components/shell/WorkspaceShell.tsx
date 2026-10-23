"use client";

import Link from "next/link";
import { UserMenu } from "./UserMenu";
import { Sidebar, type SidebarGroup } from "./Sidebar";

export type NavGroup = SidebarGroup;
export interface Crumb { label: string; href?: string }

/** The frame both workspaces share: the sidebar, a top bar with breadcrumbs and the profile menu, and the page. */
export function WorkspaceShell({ brand, role, groups, crumbs, signOutTo, menuLinks, menu, children }: {
  brand: string; role: string; groups: NavGroup[]; crumbs: Crumb[]; signOutTo: string; menu?: React.ReactNode; menuLinks?: { href: string; label: string; icon?: React.ReactNode }[]; children: React.ReactNode;
}) {
  const logo = (
    <span className="flex items-center gap-2.5">
      <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--ws-accent)] text-[12px] font-bold text-white">H</span>
      {brand} <span className="font-normal text-[#5b6f70]">{role}</span>
    </span>
  );
  return (
    <div className="ws-grid">
      <Sidebar groups={groups} brand={logo} storageKey={`sidebar:${role}`} />
      <div className="min-w-0">
        <div className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-[var(--ws-border)] bg-[#f6f8f7]/90 px-4 text-[14px] backdrop-blur sm:px-8">
          <div className="flex min-w-0 items-center gap-2">
            {crumbs.map((c, n) => (
              <span key={n} className={`flex min-w-0 items-center gap-2 ${n < crumbs.length - 1 ? "hidden sm:flex" : ""}`}>
                {n > 0 && <span className="hidden text-neutral-300 sm:inline">/</span>}
                {c.href && n < crumbs.length - 1 ? <Link href={c.href} className="text-neutral-500 hover:text-ink">{c.label}</Link> : <span className={`truncate ${n === crumbs.length - 1 ? "font-medium" : "text-neutral-500"}`}>{c.label}</span>}
              </span>
            ))}
          </div>
          {menu ?? <UserMenu signOutTo={signOutTo} links={menuLinks} />}
        </div>
        <main className="px-4 py-6 sm:px-8 sm:py-7">{children}</main>
      </div>
    </div>
  );
}

/** Title, one line of what matters now, and the main actions on the right. */
export function PageHeader({ title, sub, actions }: { title: string; sub?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0"><h1 className="text-[26px] leading-tight">{title}</h1>{sub && <p className="mt-1 text-[14px] text-mute">{sub}</p>}</div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export const greeting = (name: string | null | undefined) => {
  const h = new Date().getHours();
  return `Good ${h < 12 ? "morning" : h < 18 ? "afternoon" : "evening"}${name ? `, ${name}` : ""}`;
};
