"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { CalendarDays, LayoutDashboard, Tent, Ticket } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canHostCityEvents, canHostFests } from "@/lib/permissions";
import type { MyFest } from "@/lib/types";
import { OrganiserProfileMenu } from "@/components/shell/OrganiserProfileMenu";
import { PageHeader, WorkspaceShell, type Crumb, type NavGroup } from "@/components/shell/WorkspaceShell";
import { Pill } from "@/components/ui/bits";

/** The fests this person belongs to, shared by the sidebar and the pages. */
const FestsContext = createContext<{ fests: MyFest[] | null; reload: () => void }>({ fests: null, reload: () => {} });
export const useMyFests = () => useContext(FestsContext);

export const REVIEW_LABEL: Record<string, { label: string; tone: "neutral" | "amber" | "green" | "red" }> = {
  draft: { label: "Draft", tone: "neutral" },
  in_review: { label: "In review", tone: "amber" },
  changes_requested: { label: "Changes requested", tone: "amber" },
  approved: { label: "Approved", tone: "green" },
  rejected: { label: "Rejected", tone: "red" },
};

const ic = "h-4 w-4 shrink-0";

export function CommitteeShell({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [fests, setFests] = useState<MyFest[] | null>(null);
  const canCreate = user?.role === "organizer";
  const hostsFests = canHostFests(user);
  const hostsCity = canHostCityEvents(user);

  const reload = useCallback(() => { api<MyFest[]>("/api/fests/mine").then(setFests).catch(() => setFests([])); }, []);
  useEffect(() => { if (user) reload(); }, [user, reload, pathname]);

  // Admins have their own console; only the page of one fest is open to them (to look at it). Members who are on no fest team have nothing here.
  const inFest = /^\/dashboard\/fests\/[^/]+/.test(pathname);
  useEffect(() => {
    if (user?.role === "admin" && !inFest) router.replace("/admin");
    if (user?.role === "user" && fests && fests.length === 0) router.replace("/my-passes");
  }, [user, fests, inFest, router]);

  const slug = inFest ? pathname.split("/")[3] : null;
  const currentFest = fests?.find((f) => f.slug === slug);
  const page = pathname === "/dashboard/fests" ? { title: "Your fests", blurb: "Run events, registrations and your team in one place." }
    : pathname === "/dashboard/city-events" ? { title: "City events", blurb: "Standalone events outside a fest. HiveOut reviews each one before it goes live." } : null;

  const groups: NavGroup[] = [
    { id: "main", items: [{ href: "/dashboard", label: "Dashboard", icon: <LayoutDashboard className={ic} />, exact: true }] },
    {
      id: "fests", label: "Fests", loading: fests === null, empty: "No fests yet.",
      add: hostsFests ? { href: "/dashboard/fests#new", label: "New fest" } : undefined,
      items: [
        { href: "/dashboard/fests", label: "All fests", icon: <Tent className={ic} />, exact: true },
        ...(fests ?? []).map((f) => ({ href: `/dashboard/fests/${f.slug}`, label: f.name, dot: (f.status === "live" ? "live" : "off") as "live" | "off" })),
      ],
    },
    ...(hostsCity ? [{ id: "events", label: "Events", items: [{ href: "/dashboard/city-events", label: "City events", icon: <CalendarDays className={ic} /> }] }] : []),
    { id: "account", label: "Account", items: [{ href: "/my-passes", label: "My passes", icon: <Ticket className={ic} /> }] },
  ];
  const crumbs: Crumb[] = [{ label: "Dashboard", href: "/dashboard" }, ...(inFest ? [{ label: "Fests", href: "/dashboard/fests" }, { label: currentFest?.name ?? "Fest" }] : page ? [{ label: page.title }] : [])];

  return (
    <FestsContext.Provider value={{ fests, reload }}>
      <WorkspaceShell brand="HiveOut" role={canCreate ? "Organiser" : "Fest team"} groups={groups} crumbs={crumbs} signOutTo="/" menu={<OrganiserProfileMenu role={canCreate ? "Organiser" : "Fest team"} />}>
        {page && <PageHeader title={page.title} sub={page.blurb} />}
        {children}
      </WorkspaceShell>
    </FestsContext.Provider>
  );
}

export function ReviewPill({ status }: { status: string }) {
  const r = REVIEW_LABEL[status] ?? REVIEW_LABEL.draft;
  return <Pill tone={r.tone}>{r.label}</Pill>;
}
