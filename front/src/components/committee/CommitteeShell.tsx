"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { CalendarDays, LayoutDashboard, Plus, Tent, UserCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { MyFest } from "@/lib/types";
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

const ic = "h-[18px] w-[18px]";
const base = "flex items-center gap-3 rounded-2xl px-4 py-2.5 text-sm font-semibold transition";

export function CommitteeShell({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [fests, setFests] = useState<MyFest[] | null>(null);
  const canCreate = user?.role === "organizer";

  const reload = useCallback(() => { api<MyFest[]>("/api/fests/mine").then(setFests).catch(() => setFests([])); }, []);
  useEffect(() => { if (user) reload(); }, [user, reload, pathname]);

  // Admins have their own console; only the page of one fest is open to them (to look at it). Members who are on no fest team have nothing here.
  const inFestPage = /^\/dashboard\/fests\/[^/]+/.test(pathname);
  useEffect(() => {
    if (user?.role === "admin" && !inFestPage) router.replace("/admin");
    if (user?.role === "user" && fests && fests.length === 0) router.replace("/my-passes");
  }, [user, fests, inFestPage, router]);

  const inFest = /^\/dashboard\/fests\/[^/]+/.test(pathname);
  const header = pathname === "/dashboard"
    ? { title: "Overview", blurb: "Your fests at a glance, and what needs you." }
    : pathname === "/dashboard/fests" ? { title: "Your fests", blurb: "Run events, registrations and your team in one place." }
    : pathname === "/dashboard/city-events" ? { title: "City events", blurb: "Standalone events outside a fest. HiveOut reviews each one before it goes live." } : null;

  const main = [
    { href: "/dashboard", label: "Overview", icon: <LayoutDashboard className={ic} />, active: pathname === "/dashboard" },
    { href: "/dashboard/fests", label: "Your fests", icon: <Tent className={ic} />, active: pathname === "/dashboard/fests" },
    ...(canCreate ? [{ href: "/dashboard/city-events", label: "City events", icon: <CalendarDays className={ic} />, active: pathname === "/dashboard/city-events" }] : []),
  ];

  return (
    <FestsContext.Provider value={{ fests, reload }}>
      <div className="px-4 pb-10 sm:px-6 lg:grid lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-8">
        <aside className="lg:sticky lg:top-24 lg:h-[calc(100vh-7rem)] lg:self-start">
          <nav aria-label="Committee sections" className="no-scrollbar -mx-4 mb-6 flex gap-2 overflow-x-auto px-4 lg:hidden">
            {main.map((i) => <Link key={i.href} href={i.href} className={`${base} shrink-0 ${i.active ? "bg-ink text-white" : "text-mute hover:bg-black/5"}`}>{i.icon}{i.label}</Link>)}
            {(fests ?? []).map((f) => <Link key={f.id} href={`/dashboard/fests/${f.slug}`} className={`${base} shrink-0 ${pathname === `/dashboard/fests/${f.slug}` ? "bg-ink text-white" : "text-mute hover:bg-black/5"}`}>{f.name}</Link>)}
          </nav>

          <nav aria-label="Committee sections" className="card hidden h-full flex-col p-4 lg:flex">
            <div className="mb-4 px-3 pt-2">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-chip-ink">{canCreate ? "Organiser" : "Fest team"}</p>
              <p className="mt-1 truncate font-display text-lg font-semibold">{user?.name}</p>
              <p className="truncate text-xs text-mute">{user?.email}</p>
            </div>
            <div className="flex-1 space-y-5 overflow-y-auto">
              <div className="space-y-1">
                {main.map((i) => <Link key={i.href} href={i.href} aria-current={i.active ? "page" : undefined} className={`${base} w-full ${i.active ? "bg-ink text-white" : "text-mute hover:bg-black/5 hover:text-ink"}`}>{i.icon}{i.label}</Link>)}
              </div>
              <div className="space-y-1">
                <div className="flex items-center justify-between px-4 pb-1">
                  <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-mute">Fests</p>
                  {canCreate && <Link href="/dashboard/fests#new" aria-label="New fest" className="rounded-full p-1 text-mute hover:bg-black/5 hover:text-ink"><Plus className="h-4 w-4" /></Link>}
                </div>
                {fests === null ? <p className="px-4 text-xs text-mute">Loading…</p> : fests.length === 0 ? <p className="px-4 text-xs text-mute">No fests yet.</p> : fests.map((f) => {
                  const active = pathname === `/dashboard/fests/${f.slug}`;
                  return (
                    <Link key={f.id} href={`/dashboard/fests/${f.slug}`} aria-current={active ? "page" : undefined} className={`${base} w-full justify-between ${active ? "bg-ink text-white" : "text-mute hover:bg-black/5 hover:text-ink"}`}>
                      <span className="truncate">{f.name}</span>
                      <span className={`h-2 w-2 shrink-0 rounded-full ${f.status === "live" ? "bg-emerald-500" : "bg-neutral-300"}`} title={f.status === "live" ? "Live" : "Not live"} />
                    </Link>
                  );
                })}
              </div>
            </div>
            <div className="mt-4 space-y-1 border-t border-black/5 pt-4">
              <Link href="/my-passes" className={`${base} text-mute hover:bg-black/5 hover:text-ink`}>My passes</Link>
              <Link href="/profile" className={`${base} text-mute hover:bg-black/5 hover:text-ink`}><UserCircle className={ic} /> Profile and security</Link>
              <Link href="/" className={`${base} text-mute hover:bg-black/5 hover:text-ink`}>← Back to site</Link>
            </div>
          </nav>
        </aside>

        <section className="min-w-0 pt-2 lg:pt-0">
          {header && !inFest && (
            <header className="mb-8">
              <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">{header.title}</h1>
              <p className="mt-2 text-mute">{header.blurb}</p>
            </header>
          )}
          {children}
        </section>
      </div>
    </FestsContext.Provider>
  );
}

export function ReviewPill({ status }: { status: string }) {
  const r = REVIEW_LABEL[status] ?? REVIEW_LABEL.draft;
  return <Pill tone={r.tone}>{r.label}</Pill>;
}
