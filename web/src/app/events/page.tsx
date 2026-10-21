import type { Metadata } from "next";
import { getAllEvents } from "@/lib/api";
import { EventBrowser } from "@/components/EventBrowser";
import { EmptyState } from "@/components/ui/bits";

export const metadata: Metadata = { title: "Events", description: "Browse upcoming events across college fests on HiveOut." };
export const revalidate = 30;

export default async function EventsPage({ searchParams }: { searchParams: Promise<{ q?: string; category?: string; when?: string; free?: string }> }) {
  const sp = await searchParams;
  const events = await getAllEvents();
  return (
    <div className="mx-auto max-w-6xl px-6 pb-8 pt-8">
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-hive-ink">Browse</p>
      <h1 className="mt-1 font-display text-4xl font-black tracking-tight sm:text-5xl">Events</h1>
      <p className="mb-8 mt-3 max-w-xl text-neutral-500">Everything coming up across the fests on HiveOut.</p>
      {events === null ? (
        <EmptyState title="We could not load events" body="Please check your connection and try again in a moment." />
      ) : (
        <EventBrowser events={events} initial={{ q: sp.q, category: sp.category, when: sp.when, free: sp.free === "1" }} />
      )}
    </div>
  );
}
