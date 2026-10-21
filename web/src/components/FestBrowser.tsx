"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { College, Fest } from "@/lib/types";
import { FestCard } from "./FestCard";
import { EmptyState } from "./ui/bits";

export function FestBrowser({ fests, colleges, initialCollege }: { fests: Fest[]; colleges: College[]; initialCollege?: number }) {
  const [q, setQ] = useState("");
  const [college, setCollege] = useState<number | null>(initialCollege ?? null);
  const nameOf = (id: number | null) => colleges.find((c) => c.id === id)?.name ?? null;

  const shown = useMemo(() => {
    const term = q.trim().toLowerCase();
    return fests.filter((f) => {
      if (college !== null && f.college_id !== college) return false;
      if (!term) return true;
      return [f.name, f.tagline ?? "", nameOf(f.college_id) ?? ""].some((t) => t.toLowerCase().includes(term));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fests, q, college, colleges]);

  const used = colleges.filter((c) => fests.some((f) => f.college_id === c.id));

  return (
    <>
      <div className="glass-strong mb-5 flex h-14 items-center gap-3 rounded-full pl-5 pr-4">
        <Search className="h-5 w-5 text-neutral-400" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search fests or colleges" aria-label="Search fests" className="h-full flex-1 bg-transparent outline-none placeholder:text-neutral-400" />
      </div>
      <div className="mb-8 flex flex-wrap gap-2" role="group" aria-label="Filter by college">
        <Chip active={college === null} onClick={() => setCollege(null)}>All colleges</Chip>
        {used.map((c) => <Chip key={c.id} active={college === c.id} onClick={() => setCollege(college === c.id ? null : c.id)}>{c.name}</Chip>)}
      </div>
      {shown.length === 0 ? (
        <EmptyState title="No fests match that" body="Try a different search or clear the college filter." />
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((f) => <FestCard key={f.id} fest={f} collegeName={nameOf(f.college_id)} />)}
        </div>
      )}
    </>
  );
}

export function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full px-4 py-2 text-sm font-semibold transition ${active ? "bg-ink text-white" : "glass text-neutral-700 hover:bg-white/90"}`}
    >
      {children}
    </button>
  );
}
