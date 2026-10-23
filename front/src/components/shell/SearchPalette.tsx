"use client";

import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, CornerDownLeft, Search, Tent } from "lucide-react";
import { api } from "@/lib/api";
import type { Fest, FestEvent } from "@/lib/types";
import { formatDay } from "@/lib/format";

interface Hit { key: string; href: string; title: string; sub: string; kind: "fest" | "event" }

/** Press "/" or Cmd/Ctrl+K anywhere to jump to a fest or event. */
export function SearchPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [fests, setFests] = useState<Fest[]>([]);
  const [events, setEvents] = useState<FestEvent[]>([]);
  const [active, setActive] = useState(0);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!open) return;
    setQ(""); setActive(0);
    setTimeout(() => inputRef.current?.focus(), 50);
    if (loaded) return;
    Promise.all([api<Fest[]>("/api/fests/").catch(() => []), api<FestEvent[]>("/api/events/").catch(() => [])]).then(([f, e]) => { setFests(f); setEvents(e); setLoaded(true); });
  }, [open, loaded]);

  const hits = useMemo<Hit[]>(() => {
    const term = q.trim().toLowerCase();
    const festHits: Hit[] = fests.filter((f) => !term || `${f.name} ${f.tagline ?? ""}`.toLowerCase().includes(term)).map((f) => ({ key: `f${f.id}`, href: `/fests/${f.slug}`, title: f.name, sub: f.tagline ?? "College fest", kind: "fest" }));
    const eventHits: Hit[] = events.filter((e) => !term || `${e.title} ${e.location ?? ""} ${e.fest_name ?? ""} ${e.category ?? ""}`.toLowerCase().includes(term)).map((e) => ({ key: `e${e.id}`, href: `/events/${e.id}`, title: e.title, sub: `${formatDay(e.date)}${e.fest_name ? ` · ${e.fest_name}` : ""}`, kind: "event" }));
    return [...festHits, ...eventHits].slice(0, 8);
  }, [q, fests, events]);

  useEffect(() => { setActive(0); }, [q]);

  const go = (h: Hit | undefined) => { if (!h) return; onClose(); router.push(h.href); };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, hits.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); if (hits[active]) go(hits[active]); else { onClose(); router.push(`/events?q=${encodeURIComponent(q)}`); } }
    else if (e.key === "Escape") onClose();
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[70] flex items-start justify-center px-4 pt-[12vh]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} aria-hidden />
          <motion.div role="dialog" aria-label="Search" initial={{ y: -12, scale: 0.97, opacity: 0 }} animate={{ y: 0, scale: 1, opacity: 1 }} exit={{ y: -8, scale: 0.98, opacity: 0 }} transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }} className="glass relative w-full max-w-xl overflow-hidden rounded-3xl shadow-[var(--shadow-pop)]">
            <div className="flex items-center gap-3 border-b border-black/5 px-5">
              <Search className="h-5 w-5 text-mute" />
              <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} placeholder="Search fests, events, venues" aria-label="Search" className="h-14 flex-1 bg-transparent text-base outline-none placeholder:text-neutral-400" />
              <kbd className="hidden rounded-md bg-black/5 px-1.5 py-0.5 text-xs text-mute sm:block">esc</kbd>
            </div>
            <ul className="max-h-[50vh] overflow-y-auto p-2">
              {hits.length === 0 && <li className="px-4 py-8 text-center text-sm text-mute">{loaded ? "Nothing found. Press Enter to search all events." : "Loading…"}</li>}
              {hits.map((h, i) => (
                <li key={h.key}>
                  <button onMouseEnter={() => setActive(i)} onClick={() => go(h)} className={`flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left transition ${i === active ? "bg-black/5" : ""}`}>
                    <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${h.kind === "fest" ? "bg-chip text-chip-ink" : "bg-lilac text-violet-800"}`}>{h.kind === "fest" ? <Tent className="h-5 w-5" /> : <CalendarDays className="h-5 w-5" />}</span>
                    <span className="min-w-0 flex-1"><span className="block truncate font-semibold">{h.title}</span><span className="block truncate text-sm text-mute">{h.sub}</span></span>
                    {i === active && <CornerDownLeft className="h-4 w-4 text-mute" />}
                  </button>
                </li>
              ))}
            </ul>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
