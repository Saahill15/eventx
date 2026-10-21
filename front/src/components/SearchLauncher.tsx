"use client";

import { Search } from "lucide-react";

/** A big search field that opens the search palette. */
export function SearchLauncher({ placeholder = "Search fests, events or venues" }: { placeholder?: string }) {
  return (
    <button onClick={() => window.dispatchEvent(new Event("hiveout:search"))} className="group flex h-16 w-full items-center gap-4 rounded-full bg-white px-6 text-left shadow-[var(--shadow-card)] transition hover:shadow-[var(--shadow-pop)]">
      <Search className="h-5 w-5 text-chip-ink" />
      <span className="flex-1 truncate text-lg text-neutral-400">{placeholder}</span>
      <kbd className="hidden rounded-lg bg-wash px-2 py-1 text-sm text-mute sm:block">/</kbd>
    </button>
  );
}
