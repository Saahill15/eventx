import type { Metadata } from "next";
import { getColleges, getLiveFests } from "@/lib/api";
import { FestExplorer } from "@/components/FestExplorer";
import { EmptyState } from "@/components/ui/bits";

export const metadata: Metadata = { title: "College fests", description: "Every college fest on HiveOut, with events, schedules and registration." };
export const revalidate = 30;

export default async function FestsPage({ searchParams }: { searchParams: Promise<{ college?: string }> }) {
  const { college } = await searchParams;
  const [fests, colleges] = await Promise.all([getLiveFests(), getColleges()]);
  const initialCollege = college && /^\d+$/.test(college) ? Number(college) : undefined;
  return (
    <div className="mx-auto max-w-7xl px-5 pb-4 pt-10 sm:px-8 sm:pt-14">
      <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-amber-ink">Explore</p>
      <h1 className="mb-8 font-display text-5xl font-bold tracking-[-0.03em] sm:text-6xl">College fests</h1>
      {fests === null ? <EmptyState title="We could not load fests" body="Please check your connection and try again in a moment." /> : <FestExplorer fests={fests} colleges={colleges ?? []} initialCollege={initialCollege} />}
    </div>
  );
}
