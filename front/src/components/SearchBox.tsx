"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Search } from "lucide-react";

export function SearchBox({ placeholder = "Search fests, events or colleges", initial = "", size = "lg" }: { placeholder?: string; initial?: string; size?: "md" | "lg" }) {
  const router = useRouter();
  const [q, setQ] = useState(initial);
  return (
    <form
      role="search"
      onSubmit={(e) => { e.preventDefault(); router.push(q.trim() ? `/events?q=${encodeURIComponent(q.trim())}` : "/events"); }}
      className={`glass-strong flex w-full items-center gap-3 rounded-full pl-5 pr-2 ${size === "lg" ? "h-16" : "h-12"}`}
    >
      <Search className="h-5 w-5 shrink-0 text-neutral-400" />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={placeholder}
        aria-label="Search"
        className="h-full min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-neutral-400"
      />
      <button type="submit" className={`rounded-full bg-hive font-semibold text-ink transition hover:bg-hive-dark active:scale-[0.97] ${size === "lg" ? "flex h-12 items-center justify-center px-5 min-[400px]:px-7" : "h-9 px-5 text-sm"}`}>
        <span className="hidden min-[400px]:inline">Search</span>
        <Search className="h-4 w-4 min-[400px]:hidden" aria-hidden />
      </button>
    </form>
  );
}
