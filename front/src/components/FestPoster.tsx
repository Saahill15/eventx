"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { Building2 } from "lucide-react";
import type { Fest } from "@/lib/types";
import { PosterArt } from "./Poster";

export function FestPoster({ fest, college }: { fest: Fest; college?: string | null }) {
  return (
    <motion.div whileHover={{ y: -6 }} transition={{ type: "spring", stiffness: 300, damping: 22 }}>
      <Link href={`/fests/${fest.slug}`} className="group relative block aspect-[4/5] overflow-hidden rounded-3xl bg-wash shadow-[var(--shadow-card)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
        <div className="h-full w-full transition duration-700 group-hover:scale-105"><PosterArt id={fest.id} title={fest.name} image={fest.banner_url} kicker="College fest" showTitle={false} /></div>
        <div className="glass-photo absolute inset-x-2.5 bottom-2.5 rounded-[1.25rem] p-4">
          {college && <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-white/80"><Building2 className="h-3.5 w-3.5" />{college}</p>}
          <p className="font-display text-xl font-semibold leading-tight tracking-tight">{fest.name}</p>
          <p className="mt-1 text-xs text-white/80">{fest.event_count} event{fest.event_count === 1 ? "" : "s"}{fest.tagline ? ` · ${fest.tagline}` : ""}</p>
        </div>
      </Link>
    </motion.div>
  );
}
