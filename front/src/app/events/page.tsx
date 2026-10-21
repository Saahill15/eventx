import type { Metadata } from "next";
import { getAllEvents } from "@/lib/api";
import { EventExplorer } from "@/components/EventExplorer";
import { EmptyState } from "@/components/ui/bits";

export const metadata: Metadata = { title: "Events", description: "Browse upcoming events across college fests on HiveOut." };
export const revalidate = 30;

export default async function EventsPage({ searchParams }: { searchParams: Promise<{ q?: string; category?: string; date?: string; free?: string; view?: string }> }) {
  const sp = await searchParams;
  const events = await getAllEvents();
  return (
    <div className="mx-auto max-w-7xl px-5 pb-4 pt-10 sm:px-8 sm:pt-14">
      <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-amber-ink">Explore</p>
      <h1 className="mb-8 font-display text-5xl font-bold tracking-[-0.03em] sm:text-6xl">All events</h1>
      {events === null ? <EmptyState title="We could not load events" body="Please check your connection and try again in a moment." /> : (
        <EventExplorer events={events} initial={{ q: sp.q, category: sp.category, date: sp.date, free: sp.free === "1", view: sp.view }} />
      )}
    </div>
  );
}
