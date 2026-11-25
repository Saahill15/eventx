"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button } from "./ui/Button";

export interface TourStep {
  /** The `data-tour` name of the part of the page to point at. Without one, or if it is not on screen, the step is shown in the middle. */
  target?: string;
  title: string;
  body: React.ReactNode;
  /** A button on this step that does something useful, such as starting the first fest. */
  action?: { label: string; onClick: () => void };
}

const PAD = 8;
const GAP = 16;
const WIDTH = 360;

/**
 * A short, skippable tour: it dims the page, lights up the part being explained and says what it is for. It never changes anything
 * itself. Skip is always on screen, Escape skips, and the arrow keys move between steps.
 */
export function GuidedTour({ steps, onClose }: { steps: TourStep[]; onClose: (finished: boolean) => void }) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const card = useRef<HTMLDivElement>(null);
  const step = steps[i];
  const last = i === steps.length - 1;

  const measure = useCallback(() => {
    const el = step.target ? document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`) : null;
    if (!el || el.getClientRects().length === 0) { setRect(null); return; }
    const r = el.getBoundingClientRect();
    if (r.top < 0 || r.bottom > window.innerHeight || r.left < 0 || r.right > window.innerWidth) {
      el.scrollIntoView({ block: "center", inline: "center", behavior: "instant" as ScrollBehavior });
      setRect(el.getBoundingClientRect());
    } else setRect(r);
  }, [step.target]);

  // Find the target on each step, and keep following it if the page moves or resizes
  useLayoutEffect(() => { measure(); }, [measure]);
  useEffect(() => {
    let frame = 0;
    const again = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(measure); };
    window.addEventListener("resize", again);
    window.addEventListener("scroll", again, true);
    const settle = window.setTimeout(measure, 250); // the page may still be settling when the step opens
    return () => { window.removeEventListener("resize", again); window.removeEventListener("scroll", again, true); cancelAnimationFrame(frame); window.clearTimeout(settle); };
  }, [measure]);

  // Put the card beside the lit-up part, or in the middle when there is none (and on a phone, always at the bottom)
  useLayoutEffect(() => {
    const el = card.current;
    if (!el) return;
    const vw = window.innerWidth, vh = window.innerHeight;
    const w = Math.min(WIDTH, vw - 24), h = el.offsetHeight;
    const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(n, hi));
    if (!rect || vw < 640) { setPos({ left: (vw - w) / 2, top: !rect ? Math.max(12, (vh - h) / 2) : Math.max(12, vh - h - 16) }); return; }
    if (rect.right + GAP + w <= vw - 12) setPos({ left: rect.right + GAP, top: clamp(rect.top, 12, vh - h - 12) });
    else if (rect.bottom + GAP + h <= vh - 12) setPos({ left: clamp(rect.left, 12, vw - w - 12), top: rect.bottom + GAP });
    else if (rect.top - GAP - h >= 12) setPos({ left: clamp(rect.left, 12, vw - w - 12), top: rect.top - GAP - h });
    else setPos({ left: clamp(rect.left - GAP - w, 12, vw - w - 12), top: clamp(rect.top, 12, vh - h - 12) });
  }, [rect, i]);

  useEffect(() => { card.current?.focus(); }, [i]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose(false);
      else if (e.key === "ArrowRight") setI((n) => Math.min(n + 1, steps.length - 1));
      else if (e.key === "ArrowLeft") setI((n) => Math.max(n - 1, 0));
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose, steps.length]);

  return (
    <div className="fixed inset-0 z-[130]" role="presentation">
      {/* Blocks clicks on the page behind, so the tour is never used by accident */}
      <div className="absolute inset-0" onClick={(e) => e.stopPropagation()} aria-hidden="true" style={rect ? undefined : { background: "rgba(8,12,12,0.6)" }} />
      {rect && <div aria-hidden="true" className="pointer-events-none fixed rounded-2xl transition-all duration-200" style={{ left: rect.left - PAD, top: rect.top - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2, boxShadow: "0 0 0 9999px rgba(8,12,12,0.6), 0 0 0 3px rgba(255,255,255,0.9)" }} />}
      <div
        ref={card} tabIndex={-1} role="dialog" aria-modal="true" aria-label={`Tour: ${step.title}`} aria-live="polite"
        className="card fixed w-[min(360px,calc(100vw-24px))] space-y-3 p-5 shadow-[var(--shadow-pop)] outline-none"
        style={{ left: pos?.left ?? 12, top: pos?.top ?? 12, visibility: pos ? "visible" : "hidden" }}
      >
        <p className="text-xs font-semibold uppercase tracking-wider text-mute">{i + 1} of {steps.length}</p>
        <h2 className="font-display text-lg font-bold leading-snug tracking-tight">{step.title}</h2>
        <div className="text-sm leading-relaxed text-neutral-700">{step.body}</div>
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 pt-1">
          <button type="button" onClick={() => onClose(false)} className="whitespace-nowrap text-sm font-semibold text-mute underline underline-offset-4 hover:text-ink">Skip tour</button>
          <div className="flex flex-wrap justify-end gap-2">
            {i > 0 && <Button size="sm" variant="ghost" type="button" onClick={() => setI(i - 1)}>Back</Button>}
            {step.action && last
              ? <><Button size="sm" variant="outline" type="button" onClick={() => onClose(true)}>Finish</Button><Button size="sm" type="button" onClick={() => { onClose(true); step.action?.onClick(); }}>{step.action.label}</Button></>
              : <Button size="sm" type="button" onClick={() => (last ? onClose(true) : setI(i + 1))}>{last ? "Done" : "Next"}</Button>}
          </div>
        </div>
      </div>
    </div>
  );
}
