"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { BadgeCheck, CalendarClock, ClipboardCheck, Landmark, LayoutDashboard, ShieldAlert, Users } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AdminOverview } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { AdminProfileMenu } from "@/components/shell/AdminProfileMenu";
import { PageHeader, WorkspaceShell, type NavGroup } from "@/components/shell/WorkspaceShell";
import { CountsContext, RefreshCountsContext } from "./shared";

const ic = "h-4 w-4 shrink-0";
type Page = { href: string; label: string; title: string; blurb: string; icon: React.ReactNode; key: string; badge?: keyof AdminOverview };

const SECTIONS: { id: string; label?: string; pages: Page[] }[] = [
  { id: "main", pages: [{ href: "/admin", label: "Dashboard", title: "Dashboard", blurb: "", icon: <LayoutDashboard className={ic} />, key: "d" }] },
  { id: "review", label: "Review", pages: [
    { href: "/admin/fests", label: "Fest reviews", title: "Fest reviews", blurb: "Check submitted fests before they can go live.", icon: <ClipboardCheck className={ic} />, key: "f", badge: "fests_in_review" },
    { href: "/admin/verifications", label: "Student proofs", title: "Student proofs", blurb: "Approve or reject uploaded student IDs.", icon: <BadgeCheck className={ic} />, key: "s", badge: "verifications_pending" },
    { href: "/admin/city", label: "City events", title: "City events", blurb: "Standalone events waiting for approval.", icon: <CalendarClock className={ic} />, key: "c", badge: "city_events_pending" },
  ] },
  { id: "manage", label: "Manage", pages: [
    { href: "/admin/people", label: "People", title: "People", blurb: "Roles, college access, suspensions and sessions.", icon: <Users className={ic} />, key: "p" },
    { href: "/admin/colleges", label: "Colleges", title: "Colleges", blurb: "Partnerships and coordinator details.", icon: <Landmark className={ic} />, key: "l" },
  ] },
  { id: "security", label: "Security", pages: [{ href: "/admin/security", label: "Sign-in log", title: "Sign-in log", blurb: "Every attempt to sign in, successful or not: who, from where, and what happened.", icon: <ShieldAlert className={ic} />, key: "g" }] },
];
const ALL = SECTIONS.flatMap((s) => s.pages);

export function AdminShell({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [counts, setCounts] = useState<AdminOverview | null>(null);
  const isAdmin = user?.role === "admin";

  // Badges and the dashboard share these numbers; refresh them when the admin moves between sections or acts on something
  const refresh = useCallback(() => { api<AdminOverview>("/api/admin/overview").then(setCounts).catch(() => {}); }, []);
  useEffect(() => { if (isAdmin) refresh(); }, [isAdmin, pathname, refresh]);

  // Keyboard: press "g" and then a letter to jump (g d dashboard, g f fests, g s proofs, g c city events, g p people, g l colleges, g g sign-in log)
  useEffect(() => {
    let armed = 0;
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (e.metaKey || e.ctrlKey || e.altKey || ["INPUT", "TEXTAREA", "SELECT"].includes(el?.tagName ?? "") || el?.isContentEditable) return;
      if (e.key === "g") { armed = Date.now(); return; }
      if (armed && Date.now() - armed < 1200) {
        const hit = ALL.find((i) => i.key === e.key);
        armed = 0;
        if (hit) router.push(hit.href);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);

  if (user && !isAdmin) {
    return <div className="mx-auto max-w-md px-6 py-20 text-center"><p className="text-mute">This page is for HiveOut admins.</p><Button href="/" className="mt-6" variant="outline">Back to home</Button></div>;
  }

  const current = ALL.find((i) => (i.href === "/admin" ? pathname === "/admin" : pathname.startsWith(i.href))) ?? ALL[0];
  const groups: NavGroup[] = SECTIONS.map((s) => ({
    id: s.id, label: s.label,
    items: s.pages.map((p) => ({ href: p.href, label: p.label, icon: p.icon, badge: p.badge && counts ? counts[p.badge] : 0, exact: p.href === "/admin" })),
  }));

  return (
    <RefreshCountsContext.Provider value={refresh}>
      <CountsContext.Provider value={counts}>
        <WorkspaceShell brand="HiveOut" role="Admin" groups={groups} crumbs={[{ label: "Admin", href: "/admin" }, { label: current.title }]} signOutTo="/admin/login" menu={<AdminProfileMenu />}>
          {current.href !== "/admin" && <PageHeader title={current.title} sub={current.blurb} />}
          {children}
        </WorkspaceShell>
      </CountsContext.Provider>
    </RefreshCountsContext.Provider>
  );
}
