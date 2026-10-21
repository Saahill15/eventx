"use client";

import { motion } from "motion/react";

export function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <motion.button
      onClick={onClick}
      aria-pressed={active}
      whileTap={{ scale: 0.94 }}
      transition={{ type: "spring", stiffness: 500, damping: 28 }}
      className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold transition-colors ${active ? "bg-tint text-tint-ink ring-1 ring-brand/40" : "bg-chip text-chip-ink hover:bg-neutral-200"}`}
    >
      {children}
    </motion.button>
  );
}
