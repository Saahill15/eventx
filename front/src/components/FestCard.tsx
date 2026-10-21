import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import type { Fest } from "@/lib/types";
import { FestArt } from "./EventArt";

export function FestCard({ fest, collegeName, large = false }: { fest: Fest; collegeName?: string | null; large?: boolean }) {
  return (
    <Link
      href={`/fest/${fest.slug}`}
      className={`group relative isolate flex overflow-hidden rounded-3xl transition duration-300 hover:-translate-y-1 hover:shadow-[var(--shadow-lift)] ${large ? "min-h-[22rem] sm:min-h-[26rem]" : "min-h-[17rem]"}`}
    >
      <div className="absolute inset-0 -z-10">
        <div className="h-full w-full transition duration-700 group-hover:scale-105"><FestArt src={fest.banner_url} /></div>
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent" />
      </div>
      <div className="mt-auto w-full p-4 sm:p-5">
        <div className="glass-strong rounded-2xl p-4">
          {collegeName && <p className="text-xs font-semibold text-hive-ink">{collegeName}</p>}
          <div className="flex items-start justify-between gap-3">
            <h3 className={`font-display font-extrabold leading-tight tracking-tight ${large ? "text-2xl sm:text-3xl" : "text-xl"}`}>{fest.name}</h3>
            <ArrowUpRight className="mt-1 h-5 w-5 shrink-0 text-neutral-400 transition group-hover:text-hive-ink" />
          </div>
          {fest.tagline && <p className="mt-1 line-clamp-1 text-sm text-neutral-600">{fest.tagline}</p>}
          <p className="mt-2 text-xs font-medium text-neutral-500">{fest.event_count} event{fest.event_count === 1 ? "" : "s"}</p>
        </div>
      </div>
    </Link>
  );
}
