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
    <div className="mx-auto max-w-[1760px] px-4 pb-4 pt-8 sm:px-6 sm:pt-12">
      <div className="mb-8 text-center"><span className="inline-flex rounded-full bg-chip px-4 py-2 text-sm font-medium text-chip-ink">Explore</span></div>
      <h1 className="mb-10 text-center font-display text-5xl font-semibold tracking-[-0.03em] sm:text-7xl">All events</h1>
      {events === null ? <EmptyState title="We could not load events" body="Please check your connection and try again in a moment." /> : (
        <EventExplorer events={events} initial={{ q: sp.q, category: sp.category, date: sp.date, free: sp.free === "1", view: sp.view }} />
      )}
    </div>
  );
}
