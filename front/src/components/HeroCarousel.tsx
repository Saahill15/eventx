"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { ArrowRight, Building2 } from "lucide-react";
import { PosterArt } from "./Poster";

export interface Slide { id: number; slug: string; name: string; tagline: string | null; banner: string | null; college: string | null; events: number }

const SLIDE_MS = 6500;

/** Full-width featured-fest banner that auto-advances, pauses on hover, and can be swiped. */
export function HeroCarousel({ slides }: { slides: Slide[] }) {
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  const n = slides.length;

  useEffect(() => {
    if (paused || n < 2) return;
    const id = setTimeout(() => setI((v) => (v + 1) % n), SLIDE_MS);
    return () => clearTimeout(id);
  }, [i, paused, n]);

  if (n === 0) return null;
  const s = slides[i];

  return (
    <div onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocus={() => setPaused(true)} onBlur={() => setPaused(false)} className="relative">
      <motion.div
        drag={n > 1 ? "x" : false}
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={0.2}
        onDragEnd={(_, info) => { if (info.offset.x < -60) setI((v) => (v + 1) % n); else if (info.offset.x > 60) setI((v) => (v - 1 + n) % n); }}
        className="relative h-[26rem] overflow-hidden rounded-[2rem] bg-wash sm:h-[32rem]"
      >
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.div key={s.id} className="absolute inset-0" initial={{ opacity: 0, scale: 1.06 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}>
            <PosterArt id={s.id} title={s.name} image={s.banner} kicker="College fest" className="pointer-events-none" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/55 via-black/5 to-transparent" />
          </motion.div>
        </AnimatePresence>

        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={`c${s.id}`} initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.45, delay: 0.1 }} className="absolute inset-x-3 bottom-3 sm:inset-x-6 sm:bottom-6 sm:max-w-xl">
            <div className="glass-photo rounded-[1.5rem] p-5 sm:p-7">
              {s.college && <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-white/80"><Building2 className="h-4 w-4" />{s.college}</p>}
              <h2 className="font-display text-3xl font-bold leading-[1.05] tracking-tight sm:text-5xl">{s.name}</h2>
              {s.tagline && <p className="mt-2 line-clamp-2 text-white/80">{s.tagline}</p>}
              <div className="mt-5 flex flex-wrap items-center gap-3">
                <Link href={`/fest/${s.slug}`} className="inline-flex h-11 items-center gap-2 rounded-full bg-amber px-6 text-[0.9375rem] font-semibold text-ink transition hover:bg-amber-deep active:scale-[0.97]">Explore the fest <ArrowRight className="h-4 w-4" /></Link>
                <span className="text-sm font-medium text-white/80">{s.events} event{s.events === 1 ? "" : "s"}</span>
              </div>
            </div>
          </motion.div>
        </AnimatePresence>

        {n > 1 && (
          <div className="absolute right-4 top-4 flex gap-1.5 sm:right-6 sm:top-6" role="tablist" aria-label="Featured fests">
            {slides.map((sl, idx) => (
              <button key={sl.id} role="tab" aria-selected={idx === i} aria-label={`Show ${sl.name}`} onClick={() => setI(idx)} className="glass-photo relative h-2 w-10 overflow-hidden rounded-full">
                {idx === i && <motion.span key={`${i}-${paused}`} className="absolute inset-y-0 left-0 bg-white" initial={{ width: 0 }} animate={{ width: paused ? "100%" : "100%" }} transition={{ duration: paused ? 0 : SLIDE_MS / 1000, ease: "linear" }} />}
              </button>
            ))}
          </div>
        )}
      </motion.div>
    </div>
  );
}
