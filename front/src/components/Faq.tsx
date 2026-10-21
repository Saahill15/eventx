"use client";

import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { Plus } from "lucide-react";

export function Faq({ items }: { items: { q: string; a: string }[] }) {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div className="divide-y divide-black/5">
      {items.map((it, i) => (
        <div key={it.q}>
          <button onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i} className="flex w-full items-center justify-between gap-4 py-5 text-left">
            <span className="font-display text-lg font-semibold tracking-tight sm:text-xl">{it.q}</span>
            <motion.span animate={{ rotate: open === i ? 45 : 0 }} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-chip text-chip-ink"><Plus className="h-4 w-4" /></motion.span>
          </button>
          <AnimatePresence initial={false}>
            {open === i && (
              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }} className="overflow-hidden">
                <p className="max-w-2xl pb-5 leading-relaxed text-mute">{it.a}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ))}
    </div>
  );
}
