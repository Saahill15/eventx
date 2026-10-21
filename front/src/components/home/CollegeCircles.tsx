import Link from "next/link";
import type { College } from "@/lib/types";

const initials = (name: string) => name.replace(/[^A-Za-z ]/g, "").split(" ").filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

/** Round college badges in a softly tinted band, like the artists row on District. */
export function CollegeCircles({ colleges }: { colleges: College[] }) {
  return (
    <section className="rounded-[1.75rem] bg-tint/60 px-5 py-8 sm:px-10">
      <h2 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">Colleges on HiveOut</h2>
      <div className="no-scrollbar -mx-5 mt-6 flex gap-5 overflow-x-auto px-5 pb-1 sm:mx-0 sm:px-0">
        {colleges.map((c) => (
          <Link key={c.id} href={`/fests?college=${c.id}`} className="group flex w-24 shrink-0 flex-col items-center gap-3 text-center">
            <span className="flex h-20 w-20 items-center justify-center rounded-full bg-white font-display text-2xl font-semibold shadow-[var(--shadow-card)] ring-1 ring-black/5 transition group-hover:-translate-y-1 group-hover:ring-brand">{initials(c.name)}</span>
            <span className="text-sm font-semibold leading-tight">{c.name}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
