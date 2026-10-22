"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { BadgeCheck, CalendarClock, ClipboardCheck, Landmark, LayoutDashboard, ShieldAlert, UserCircle, Users } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AdminOverview } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { CountsContext, RefreshCountsContext } from "./shared";

type Item = { href: string; label: string; title: string; blurb: string; icon: React.ReactNode; badge?: keyof AdminOverview };
const group = (name: string, items: Item[]) => ({ name, items });
const ic = "h-[18px] w-[18px]";

const GROUPS = [
  group("", [{ href: "/admin", label: "Overview", title: "Overview", blurb: "How the platform is doing, and what needs you.", icon: <LayoutDashboard className={ic} /> }]),
  group("Review", [
    { href: "/admin/fests", label: "Fest reviews", title: "Fest reviews", blurb: "Check submitted fests before they can go live.", icon: <ClipboardCheck className={ic} />, badge: "fests_in_review" },
    { href: "/admin/verifications", label: "Student proofs", title: "Student proofs", blurb: "Approve or reject uploaded student IDs.", icon: <BadgeCheck className={ic} />, badge: "verifications_pending" },
    { href: "/admin/city", label: "City events", title: "City events", blurb: "Standalone events waiting for approval.", icon: <CalendarClock className={ic} />, badge: "city_events_pending" },
  ]),
  group("Manage", [
    { href: "/admin/people", label: "People", title: "People", blurb: "Roles, college access, suspensions and sessions.", icon: <Users className={ic} /> },
    { href: "/admin/colleges", label: "Colleges", title: "Colleges", blurb: "Partnerships and coordinator details.", icon: <Landmark className={ic} /> },
  ]),
  group("Security", [
    { href: "/admin/security", label: "Sign-in log", title: "Sign-in log", blurb: "Every attempt to sign in, successful or not: who, from where, and what happened.", icon: <ShieldAlert className={ic} /> },
  ]),
];
const ALL = GROUPS.flatMap((g) => g.items);

export function AdminShell({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const pathname = usePathname();
  const [counts, setCounts] = useState<AdminOverview | null>(null);
  const isAdmin = user?.role === "admin";

  // Badges and the overview share these numbers; refresh them when the admin moves between sections or acts on something
  const refresh = useCallback(() => { api<AdminOverview>("/api/admin/overview").then(setCounts).catch(() => {}); }, []);
  useEffect(() => { if (isAdmin) refresh(); }, [isAdmin, pathname, refresh]);

  // On a phone the section row scrolls sideways: keep the current section in view
  useEffect(() => {
    document.querySelector<HTMLElement>("[data-mobile-nav] [aria-current]")?.scrollIntoView({ inline: "center", block: "nearest" });
  }, [pathname]);

  if (user && !isAdmin) {
    return <div className="mx-auto max-w-md px-6 py-20 text-center"><p className="text-mute">This page is for HiveOut admins.</p><Button href="/" className="mt-6" variant="outline">Back to home</Button></div>;
  }

  const current = ALL.find((i) => (i.href === "/admin" ? pathname === "/admin" : pathname.startsWith(i.href))) ?? ALL[0];
  const link = (i: Item, mobile = false) => {
    const active = i === current;
    const n = i.badge && counts ? counts[i.badge] : 0;
    return (
      <Link key={i.href} href={i.href} aria-current={active ? "page" : undefined}
        className={`flex shrink-0 items-center gap-3 rounded-2xl px-4 py-2.5 text-sm font-semibold transition ${active ? "bg-ink text-white" : "text-mute hover:bg-black/5 hover:text-ink"} ${mobile ? "" : "w-full"}`}>
        {i.icon}
        <span className="flex-1 whitespace-nowrap">{i.label}</span>
        {!!n && <span className="rounded-full bg-brand px-2 py-0.5 text-xs font-bold text-on-brand">{String(n)}</span>}
      </Link>
    );
  };

  return (
    <RefreshCountsContext.Provider value={refresh}><CountsContext.Provider value={counts}>
      <div className="px-4 pb-10 sm:px-6 lg:grid lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-8">
        <aside className="lg:sticky lg:top-24 lg:h-[calc(100vh-7rem)] lg:self-start">
          {/* Phones and tablets: one scrolling row. Desktop: a sidebar. */}
          <nav data-mobile-nav aria-label="Admin sections" className="no-scrollbar -mx-4 mb-6 flex gap-2 overflow-x-auto px-4 lg:hidden">{ALL.map((i) => link(i, true))}</nav>
          <nav aria-label="Admin sections" className="card hidden h-full flex-col p-4 lg:flex">
            <div className="mb-4 px-3 pt-2">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-chip-ink">Admin</p>
              <p className="mt-1 truncate font-display text-lg font-semibold">{user?.name}</p>
              <p className="truncate text-xs text-mute">{user?.email}</p>
            </div>
            <div className="flex-1 space-y-5 overflow-y-auto">
              {GROUPS.map((g) => (
                <div key={g.name || "main"} className="space-y-1">
                  {g.name && <p className="px-4 pb-1 text-[11px] font-bold uppercase tracking-[0.14em] text-mute">{g.name}</p>}
                  {g.items.map((i) => link(i))}
                </div>
              ))}
            </div>
            <div className="mt-4 space-y-1 border-t border-black/5 pt-4">
              <Link href="/profile" className="flex items-center gap-3 rounded-2xl px-4 py-2.5 text-sm font-semibold text-mute transition hover:bg-black/5 hover:text-ink"><UserCircle className={ic} /> Profile and security</Link>
              <Link href="/" className="flex items-center gap-3 rounded-2xl px-4 py-2.5 text-sm font-semibold text-mute transition hover:bg-black/5 hover:text-ink">← Back to site</Link>
            </div>
          </nav>
        </aside>

        <section className="min-w-0 pt-2 lg:pt-0">
          <header className="mb-8">
            <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">{current.title}</h1>
            <p className="mt-2 text-mute">{current.blurb}</p>
          </header>
          {children}
        </section>
      </div>
    </CountsContext.Provider></RefreshCountsContext.Provider>
  );
}
