"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { College, Fest } from "@/lib/types";
import { AnimatedList } from "./AnimatedList";
import { FestPoster } from "./FestPoster";
import { Chip } from "./ui/Chip";
import { EmptyState } from "./ui/bits";

export function FestExplorer({ fests, colleges, initialCollege }: { fests: Fest[]; colleges: College[]; initialCollege?: number }) {
  const [q, setQ] = useState("");
  const [college, setCollege] = useState<number | null>(initialCollege ?? null);
  const nameOf = (id: number | null) => colleges.find((c) => c.id === id)?.name ?? null;

  const shown = useMemo(() => {
    const term = q.trim().toLowerCase();
    return fests.filter((f) => (college === null || f.college_id === college) && (!term || [f.name, f.tagline ?? "", colleges.find((c) => c.id === f.college_id)?.name ?? ""].some((t) => t.toLowerCase().includes(term))));
  }, [fests, colleges, q, college]);
  const used = colleges.filter((c) => fests.some((f) => f.college_id === c.id));

  return (
    <div>
      <div className="card mb-6 space-y-4 p-4 sm:p-6"><label className="flex h-14 items-center gap-3 rounded-full bg-wash px-5 focus-within:ring-4 focus-within:ring-brand/25">
        <Search className="h-5 w-5 text-brand" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search fests or colleges" aria-label="Search fests" className="h-full flex-1 bg-transparent text-base outline-none placeholder:text-neutral-400" />
      </label>
      <div className="no-scrollbar flex gap-2 overflow-x-auto" role="group" aria-label="Filter by college">
        <Chip active={college === null} onClick={() => setCollege(null)}>All colleges</Chip>
        {used.map((c) => <Chip key={c.id} active={college === c.id} onClick={() => setCollege(college === c.id ? null : c.id)}>{c.name}</Chip>)}
      </div></div>
      {shown.length === 0 ? <EmptyState title="No fests match that" body="Try a different search or clear the college filter." /> : (
        <AnimatedList items={shown} getKey={(f) => f.id} render={(f) => <FestPoster fest={f} college={nameOf(f.college_id)} />} className="grid grid-cols-2 gap-4 sm:gap-5 md:grid-cols-3 lg:grid-cols-4" />
      )}
    </div>
  );
}
