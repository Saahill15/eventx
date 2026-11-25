"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, createContext, useCallback, useContext, useEffect, useState } from "react";
import { CalendarDays, LayoutDashboard, Tent, Ticket } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canHostCityEvents, canHostFests } from "@/lib/permissions";
import type { MyFest } from "@/lib/types";
import { OrganiserProfileMenu } from "@/components/shell/OrganiserProfileMenu";
import { PageHeader, WorkspaceShell, type Crumb, type NavGroup } from "@/components/shell/WorkspaceShell";
import { Pill } from "@/components/ui/bits";
import { GuidedTour, type TourStep } from "@/components/GuidedTour";

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

/** Opens the welcome tour whenever the address is /dashboard?tour=1, even if the page was already open. */
function TourTrigger({ onStart }: { onStart: () => void }) {
  const params = useSearchParams();
  const pathname = usePathname();
  useEffect(() => { if (pathname === "/dashboard" && params.get("tour") === "1") onStart(); }, [params, pathname, onStart]);
  return null;
}

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

  // The welcome tour: opened by the welcome pop-up or "Take the tour again" in the account menu (both go to /dashboard?tour=1)
  const [touring, setTouring] = useState(false);
  const startTour = useCallback(() => setTouring(true), []);
  const endTour = (finished: boolean) => { setTouring(false); window.history.replaceState(null, "", "/dashboard"); void finished; };
  const first = user?.first_name ?? user?.name?.split(" ")[0];
  const tour: TourStep[] = [
    { title: `Welcome to HiveOut${first ? `, ${first}` : ""}`, body: "Here is a one-minute look at where things are. You can skip at any time, and take it again later from your account menu." },
    { target: "nav-fests", title: "Your fests live here", body: "Every fest you create is listed here, with a green dot once it is live for students. Open one to run it." },
    ...(hostsFests ? [{ target: "nav-fests-add", title: "Start a fest with the +", body: "You only need a name and, if you know them, the dates. Your fest stays a private draft until HiveOut approves it, so nothing goes public by accident." }] : []),
    { target: "account-menu", title: "Your account", body: "Your notifications, profile and sign out are here, and so is this tour if you want it again." },
    {
      title: "How a fest goes live",
      body: (<ol className="list-decimal space-y-1.5 pl-5"><li><strong>Create it:</strong> a name, your college and the dates.</li><li><strong>Fill it in:</strong> banner, venue, contact and your events.</li><li><strong>Send it for review:</strong> the HiveOut team checks it.</li><li><strong>Go live:</strong> students find it and register.</li></ol>),
      ...(hostsFests ? { action: { label: "Create my first fest", onClick: () => router.push("/dashboard/fests#new") } } : {}),
    },
  ];

  const groups: NavGroup[] = [
    { id: "main", items: [{ href: "/dashboard", label: "Dashboard", icon: <LayoutDashboard className={ic} />, exact: true }] },
    {
      id: "fests", label: "Fests", tour: "nav-fests", loading: fests === null, empty: "No fests yet.",
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
        <Suspense fallback={null}><TourTrigger onStart={startTour} /></Suspense>
        {touring && <GuidedTour steps={tour} onClose={endTour} />}
      </WorkspaceShell>
    </FestsContext.Provider>
  );
}

export function ReviewPill({ status }: { status: string }) {
  const r = REVIEW_LABEL[status] ?? REVIEW_LABEL.draft;
  return <Pill tone={r.tone}>{r.label}</Pill>;
}
