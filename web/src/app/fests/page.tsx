import type { Metadata } from "next";
import { getColleges, getLiveFests } from "@/lib/api";
import { FestBrowser } from "@/components/FestBrowser";
import { EmptyState } from "@/components/ui/bits";

export const metadata: Metadata = { title: "College fests", description: "Every college fest on HiveOut, with events, schedules and registration." };
export const revalidate = 30;

export default async function FestsPage({ searchParams }: { searchParams: Promise<{ college?: string }> }) {
  const { college } = await searchParams;
  const [fests, colleges] = await Promise.all([getLiveFests(), getColleges()]);
  const initialCollege = college && /^\d+$/.test(college) ? Number(college) : undefined;

  return (
    <div className="mx-auto max-w-6xl px-6 pb-8 pt-8">
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-hive-ink">Browse</p>
      <h1 className="mt-1 font-display text-4xl font-black tracking-tight sm:text-5xl">College fests</h1>
      <p className="mb-8 mt-3 max-w-xl text-neutral-500">Find a fest, see what is on, and register for the events you want.</p>
      {fests === null ? (
        <EmptyState title="We could not load fests" body="Please check your connection and try again in a moment." />
      ) : (
        <FestBrowser fests={fests} colleges={colleges ?? []} initialCollege={initialCollege} />
      )}
    </div>
  );
}
