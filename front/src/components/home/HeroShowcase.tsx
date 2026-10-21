"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { CalendarDays, MapPin, Ticket } from "lucide-react";
import { PosterArt } from "../Poster";
import { FadeUp } from "../motion";
import { InfoChip } from "../ui/bits";

export function HeroShowcase({ photo }: { photo: { id: number; title: string; image: string | null } | null }) {
  return (
    <section className="dots relative overflow-hidden px-4 pb-20 pt-12 text-center sm:pt-20">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[28rem] bg-gradient-to-b from-white/70 to-transparent" aria-hidden />
      <div className="relative mx-auto max-w-5xl">
        <FadeUp className="flex flex-wrap justify-center gap-2.5">
          <InfoChip icon={<CalendarDays className="h-4 w-4" />}>College fest season</InfoChip>
          <InfoChip icon={<MapPin className="h-4 w-4" />}>Mumbai, India</InfoChip>
        </FadeUp>

        <FadeUp delay={0.08}>
          <h1 className="mt-7 font-display text-[3.2rem] font-semibold leading-[1.02] tracking-[-0.03em] sm:text-7xl lg:text-[6.25rem]">
            Every college
            <span className="mt-1 flex flex-wrap items-center justify-center gap-x-4 sm:gap-x-6">
              <span>fest</span>
              {photo && (
                <motion.span
                  initial={{ rotate: 12, scale: 0.7, opacity: 0 }}
                  animate={{ rotate: 8, scale: 1, opacity: 1 }}
                  whileHover={{ rotate: -4, scale: 1.08 }}
                  transition={{ type: "spring", stiffness: 180, damping: 14, delay: 0.35 }}
                  className="inline-block h-14 w-20 overflow-hidden rounded-2xl shadow-[var(--shadow-pop)] ring-4 ring-white sm:h-24 sm:w-36 sm:rounded-3xl"
                >
                  <PosterArt id={photo.id} title={photo.title} image={photo.image} />
                </motion.span>
              )}
              <span>in one place</span>
            </span>
          </h1>
        </FadeUp>

        <FadeUp delay={0.16}>
          <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-mute">Find what is happening, register in seconds and walk in with a QR pass. Free for students and committees.</p>
        </FadeUp>
        <FadeUp delay={0.24} className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link href="/fests" className="inline-flex h-14 items-center gap-3 rounded-full bg-brand px-8 text-base font-semibold text-white shadow-[var(--shadow-glow)] transition hover:bg-brand-deep active:scale-[0.97]">Explore fests <Ticket className="h-5 w-5" /></Link>
          <Link href="/events" className="inline-flex h-14 items-center gap-3 rounded-full bg-white px-8 text-base font-semibold text-ink shadow-[var(--shadow-card)] transition hover:bg-wash active:scale-[0.97]">Browse events <CalendarDays className="h-5 w-5 text-brand" /></Link>
        </FadeUp>
      </div>
    </section>
  );
}
