"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { Sparkles } from "lucide-react";
import { FadeUp } from "./motion";
import { SearchBox } from "./SearchBox";

const CHIPS = [
  { label: "This week", href: "/events?when=week" },
  { label: "Free", href: "/events?free=1" },
  { label: "Cultural", href: "/events?category=Cultural" },
  { label: "Technical", href: "/events?category=Technical" },
  { label: "Music", href: "/events?category=Music" },
  { label: "Sports", href: "/events?category=Sports" },
];

function Hexagon({ className, delay = 0, duration = 7 }: { className: string; delay?: number; duration?: number }) {
  return (
    <motion.svg
      viewBox="0 0 100 115" aria-hidden
      className={`pointer-events-none absolute ${className}`}
      animate={{ y: [0, -14, 0], rotate: [0, 4, 0] }}
      transition={{ duration, delay, repeat: Infinity, ease: "easeInOut" }}
    >
      <path d="M50 4 94 29v57L50 111 6 86V29z" fill="currentColor" />
    </motion.svg>
  );
}

export function Hero() {
  return (
    <section className="relative mx-auto max-w-6xl overflow-hidden px-6 pb-16 pt-10 text-center sm:pt-16">
      <Hexagon className="-left-4 top-24 h-16 w-16 text-hive/30 sm:left-6 sm:h-24 sm:w-24" />
      <Hexagon className="-right-3 top-52 h-14 w-14 text-hive/20 sm:right-10 sm:h-20 sm:w-20" delay={1.5} duration={8} />
      <Hexagon className="left-[18%] top-[26rem] hidden h-10 w-10 text-hive/25 md:block" delay={0.8} duration={6} />

      <FadeUp>
        <p className="glass mx-auto mb-6 inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium text-neutral-600">
          <Sparkles className="h-4 w-4 text-hive-ink" /> College fest season is here
        </p>
      </FadeUp>
      <FadeUp delay={0.08}>
        <h1 className="mx-auto max-w-3xl font-display text-[2.6rem] font-black leading-[1.03] tracking-tight sm:text-6xl lg:text-7xl">
          Every college fest.{" "}
          <motion.span
            className="inline-block whitespace-nowrap rounded-2xl bg-hive px-3 [box-decoration-break:clone]"
            initial={{ scale: 0.9, rotate: -2, opacity: 0 }}
            animate={{ scale: 1, rotate: 0, opacity: 1 }}
            transition={{ type: "spring", stiffness: 220, damping: 16, delay: 0.45 }}
          >
            One place.
          </motion.span>
        </h1>
      </FadeUp>
      <FadeUp delay={0.18}>
        <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-neutral-500">
          Find what is happening, register in seconds, and walk in with a QR pass. Free for students.
        </p>
      </FadeUp>
      <FadeUp delay={0.28} className="mx-auto mt-9 max-w-2xl"><SearchBox /></FadeUp>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        {CHIPS.map((chip, i) => (
          <motion.div key={chip.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 + i * 0.05, duration: 0.4 }} whileHover={{ y: -2 }} whileTap={{ scale: 0.96 }}>
            <Link href={chip.href} className="glass block rounded-full px-4 py-2 text-sm font-medium text-neutral-700 transition hover:bg-white/90">{chip.label}</Link>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
