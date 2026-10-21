"use client";

import { motion } from "motion/react";
import { QRCodeSVG } from "qrcode.react";

/** Decorative pass shown on the home page; tilts as you move over it. */
export function MiniTicket() {
  return (
    <motion.div whileHover={{ rotate: -2, y: -6 }} initial={{ rotate: 4 }} animate={{ rotate: 3 }} transition={{ type: "spring", stiffness: 200, damping: 14 }} className="mx-auto w-56 rounded-3xl bg-white p-4 shadow-[var(--shadow-pop)] ring-1 ring-black/5">
      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-amber-ink">Fest pass</p>
      <p className="font-display text-xl font-bold leading-tight tracking-tight">Your fest</p>
      <div className="my-3 border-t-2 border-dashed border-black/10" />
      <QRCodeSVG value="hiveout-demo-pass" size={168} className="mx-auto" />
      <p className="mt-3 text-center text-xs font-semibold text-emerald-700">Valid · tap to enter</p>
    </motion.div>
  );
}
