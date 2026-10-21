"use client";

import { MotionConfig, motion, type HTMLMotionProps, type Variants } from "motion/react";
import type { ReactNode } from "react";

export const EASE = [0.22, 1, 0.36, 1] as const;

/** Wraps the app so every animation respects the visitor's reduce-motion setting. */
export function MotionProvider({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

/** Fades and lifts content into view as it scrolls on screen. */
export function Reveal({ children, delay = 0, y = 28, className, ...rest }: { children: ReactNode; delay?: number; y?: number; className?: string } & Omit<HTMLMotionProps<"div">, "children">) {
  return (
    <motion.div className={className} initial={{ opacity: 0, y }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "0px 0px -70px 0px" }} transition={{ duration: 0.65, delay, ease: EASE }} {...rest}>
      {children}
    </motion.div>
  );
}

const container: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } };
const item: Variants = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: EASE } } };

export function Stagger({ children, className }: { children: ReactNode; className?: string }) {
  return <motion.div className={className} variants={container} initial="hidden" whileInView="show" viewport={{ once: true, margin: "0px 0px -70px 0px" }}>{children}</motion.div>;
}
export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return <motion.div className={className} variants={item}>{children}</motion.div>;
}

export function FadeUp({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return <motion.div className={className} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay, ease: EASE }}>{children}</motion.div>;
}

export { motion };
