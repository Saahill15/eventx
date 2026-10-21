"use client";

import { AnimatePresence, motion } from "motion/react";
import type { ReactNode } from "react";

/** A list or grid whose items animate in, out and into new positions when filters change. */
export function AnimatedList<T>({ items, getKey, render, className }: { items: T[]; getKey: (item: T) => string | number; render: (item: T) => ReactNode; className: string }) {
  return (
    <motion.div layout className={className}>
      <AnimatePresence mode="popLayout" initial={false}>
        {items.map((item) => (
          <motion.div key={getKey(item)} layout initial={{ opacity: 0, scale: 0.97, y: 14 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.97 }} transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}>
            {render(item)}
          </motion.div>
        ))}
      </AnimatePresence>
    </motion.div>
  );
}
