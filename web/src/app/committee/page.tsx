import type { Metadata } from "next";
import { LayoutDashboard } from "lucide-react";
import { Button } from "@/components/ui/Button";

export const metadata: Metadata = { title: "Committee dashboard", robots: { index: false } };

// Step 2 of the rebuild moves the committee tools into this app. Until then the existing dashboard is linked.
const DASHBOARD_URL = process.env.NEXT_PUBLIC_COMMITTEE_URL ?? "http://localhost:5173/organizer";

export default function CommitteePage() {
  return (
    <div className="mx-auto max-w-xl px-6 py-16 text-center">
      <div className="glass-strong rounded-[2rem] p-10">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-hive-100 text-hive-ink"><LayoutDashboard className="h-7 w-7" /></div>
        <h1 className="font-display text-3xl font-black tracking-tight">Committee dashboard</h1>
        <p className="mb-7 mt-3 text-neutral-500">
          Manage your fest, events, registrations and team. The new dashboard is being rebuilt in this design. For now it opens in the existing app, and you may need to sign in again there.
        </p>
        <Button href={DASHBOARD_URL} size="lg">Open the dashboard</Button>
      </div>
    </div>
  );
}
