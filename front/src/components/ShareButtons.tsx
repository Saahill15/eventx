"use client";

import { useState } from "react";
import { CalendarPlus, Check, Share2 } from "lucide-react";

interface CalendarInfo { title: string; date: string; time: string | null; location: string | null; description: string | null }

const stamp = (date: string, time: string | null) => {
  const [h, m] = (time && /^\d{1,2}:\d{2}/.test(time) ? time : "09:00").split(":");
  return `${date.slice(0, 10).replaceAll("-", "")}T${h.padStart(2, "0")}${m.slice(0, 2)}00`;
};
const esc = (t: string) => t.replace(/\\/g, "\\\\").replace(/[,;]/g, (c) => `\\${c}`).replace(/\r?\n/g, "\\n");

function downloadIcs(info: CalendarInfo) {
  const start = stamp(info.date, info.time);
  const [h, m] = (info.time ?? "09:00").split(":").map(Number);
  const end = start.slice(0, 9) + `${String((h + 2) % 24).padStart(2, "0")}${String(m || 0).padStart(2, "0")}00`;
  const lines = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//HiveOut//EN", "BEGIN:VEVENT",
    `UID:${start}-${esc(info.title).slice(0, 20)}@hiveout`, `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`,
    `DTSTART:${start}`, `DTEND:${end}`, `SUMMARY:${esc(info.title)}`,
    ...(info.location ? [`LOCATION:${esc(info.location)}`] : []),
    ...(info.description ? [`DESCRIPTION:${esc(info.description.slice(0, 500))}`] : []),
    "END:VEVENT", "END:VCALENDAR",
  ];
  const url = URL.createObjectURL(new Blob([lines.join("\r\n")], { type: "text/calendar" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `${info.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.ics`;
  a.click();
  URL.revokeObjectURL(url);
}

export function ShareButtons({ title, calendar }: { title: string; calendar?: CalendarInfo }) {
  const [copied, setCopied] = useState(false);
  const share = async () => {
    const url = window.location.href;
    if (navigator.share) { try { await navigator.share({ title, url }); return; } catch { /* cancelled: fall through to copy */ } }
    try { await navigator.clipboard.writeText(url); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* clipboard blocked */ }
  };
  const btn = "inline-flex h-12 items-center gap-2 rounded-full bg-white px-5 text-sm font-semibold shadow-[var(--shadow-card)] transition hover:bg-wash active:scale-[0.97]";
  return (
    <div className="flex flex-wrap gap-2">
      <button onClick={share} className={btn}>{copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Share2 className="h-4 w-4 text-brand" />} {copied ? "Link copied" : "Share"}</button>
      {calendar && <button onClick={() => downloadIcs(calendar)} className={btn}><CalendarPlus className="h-4 w-4 text-brand" /> Add to calendar</button>}
    </div>
  );
}
