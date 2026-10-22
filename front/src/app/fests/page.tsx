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
    <div className="mx-auto max-w-[1760px] px-4 pb-4 pt-8 sm:px-6 sm:pt-12">
      <div className="mb-8 text-center"><span className="inline-flex rounded-full bg-chip px-4 py-2 text-sm font-medium text-chip-ink">Explore</span></div>
      <h1 className="mb-10 text-center font-display text-5xl font-semibold tracking-[-0.03em] sm:text-7xl">College fests</h1>
      {fests === null ? <EmptyState title="We could not load fests" body="Please check your connection and try again in a moment." /> : <FestExplorer fests={fests} colleges={colleges ?? []} initialCollege={initialCollege} />}
    </div>
  );
}
