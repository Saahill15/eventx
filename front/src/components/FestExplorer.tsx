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
      <label className="hairline mb-5 flex h-14 items-center gap-3 rounded-full bg-white px-5 shadow-[var(--shadow-soft)] focus-within:ring-4 focus-within:ring-amber/30">
        <Search className="h-5 w-5 text-mute" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search fests or colleges" aria-label="Search fests" className="h-full flex-1 bg-transparent text-base outline-none placeholder:text-neutral-400" />
      </label>
      <div className="no-scrollbar -mx-5 mb-8 flex gap-2 overflow-x-auto px-5 sm:-mx-8 sm:px-8" role="group" aria-label="Filter by college">
        <Chip active={college === null} onClick={() => setCollege(null)}>All colleges</Chip>
        {used.map((c) => <Chip key={c.id} active={college === c.id} onClick={() => setCollege(college === c.id ? null : c.id)}>{c.name}</Chip>)}
      </div>
      {shown.length === 0 ? <EmptyState title="No fests match that" body="Try a different search or clear the college filter." /> : (
        <AnimatedList items={shown} getKey={(f) => f.id} render={(f) => <FestPoster fest={f} college={nameOf(f.college_id)} />} className="grid grid-cols-2 gap-4 sm:gap-5 md:grid-cols-3 lg:grid-cols-4" />
      )}
    </div>
  );
}
