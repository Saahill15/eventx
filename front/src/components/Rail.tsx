"use client";

import { useRef } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

/** A horizontal shelf of cards. Swipes on touch, snaps, and has arrows on desktop. */
export function Rail({ children, label }: { children: React.ReactNode; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const move = (dir: 1 | -1) => ref.current?.scrollBy({ left: dir * (ref.current.clientWidth * 0.8), behavior: "smooth" });
  const arrow = "hairline hidden h-10 w-10 items-center justify-center rounded-full bg-white shadow-[var(--shadow-soft)] transition hover:bg-wash md:flex";
  return (
    <div className="group/rail relative">
      <div ref={ref} role="list" aria-label={label} className="no-scrollbar -mx-5 flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-smooth px-5 pb-6 pt-2 sm:-mx-8 sm:gap-5 sm:px-8">
        {children}
      </div>
      <div className="pointer-events-none absolute -top-14 right-0 flex gap-2">
        <button onClick={() => move(-1)} aria-label="Scroll left" className={`${arrow} pointer-events-auto`}><ChevronLeft className="h-5 w-5" /></button>
        <button onClick={() => move(1)} aria-label="Scroll right" className={`${arrow} pointer-events-auto`}><ChevronRight className="h-5 w-5" /></button>
      </div>
    </div>
  );
}

export function RailItem({ children, className = "w-[62vw] max-w-[17rem] sm:w-64" }: { children: React.ReactNode; className?: string }) {
  return <div role="listitem" className={`shrink-0 snap-start ${className}`}>{children}</div>;
}
