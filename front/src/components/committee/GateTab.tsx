"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, CheckCircle2, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import type { FestEvent, GatePass } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/bits";

interface Result { ok: boolean; text: string; sub?: string; code?: string; undoable?: boolean }
interface Detector { detect: (v: HTMLVideoElement) => Promise<{ rawValue: string }[]> }

/** Day-of-fest check-in: scan or type a pass code to let people in at the entrance, or to mark attendance at an event. */
export function GateTab({ slug, events, canUndo }: { slug: string; events: FestEvent[]; canUndo: boolean }) {
  const [where, setWhere] = useState("entrance");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [log, setLog] = useState<Result[]>([]);
  const [camera, setCamera] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const cameraSupported = typeof window !== "undefined" && "BarcodeDetector" in window;
  const input = useRef<HTMLInputElement>(null);

  const record = useCallback((r: Result) => { setResult(r); if (r.ok) setLog((l) => [r, ...l].slice(0, 8)); }, []);

  const submit = useCallback(async (raw: string, lookupOnly = false) => {
    const value = raw.trim();
    if (value.length < 8) return;
    setBusy(true);
    try {
      if (lookupOnly) {
        const p = await api<GatePass>(`/api/fests/${slug}/gate/lookup?code=${encodeURIComponent(value)}`);
        setResult({ ok: p.status === "approved" && !p.checked_in, text: p.user_name ?? "Unknown", sub: `${p.user_email ?? ""} · ${p.status !== "approved" ? "pass blocked" : p.checked_in ? "already checked in" : "not yet checked in"}` });
      } else if (where === "entrance") {
        const p = await api<GatePass>(`/api/fests/${slug}/gate/check-in`, { method: "POST", body: { qr_code: value } });
        record({ ok: true, text: `${p.user_name} is in`, sub: p.user_email ?? undefined, code: value, undoable: canUndo });
      } else {
        const r = await api<{ user_name: string | null }>(`/api/fest-events/${where}/check-in`, { method: "POST", body: { qr_code: value } });
        record({ ok: true, text: `${r.user_name} marked present`, sub: events.find((e) => String(e.id) === where)?.title });
      }
      setCode("");
    } catch (e) { setResult({ ok: false, text: e instanceof Error ? e.message : "That did not work." }); }
    setBusy(false);
    input.current?.focus();
  }, [slug, where, canUndo, events, record]);

  const undo = async (c: string) => {
    try { await api(`/api/fests/${slug}/gate/undo`, { method: "POST", body: { qr_code: c } }); setResult({ ok: true, text: "Check-in undone" }); setLog((l) => l.filter((x) => x.code !== c)); }
    catch (e) { setResult({ ok: false, text: e instanceof Error ? e.message : "Could not undo." }); }
  };

  // Camera scanning, where the browser can read QR codes itself
  useEffect(() => {
    if (!camera) return;
    let stream: MediaStream | null = null; let timer = 0; let last = ""; let stopped = false;
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (stopped || !video.current) return;
        video.current.srcObject = stream; await video.current.play();
        const Detector = (window as unknown as { BarcodeDetector: new (o: { formats: string[] }) => Detector }).BarcodeDetector;
        const detector = new Detector({ formats: ["qr_code"] });
        timer = window.setInterval(async () => {
          if (!video.current) return;
          const found = await detector.detect(video.current).catch(() => []);
          if (found[0] && found[0].rawValue !== last) { last = found[0].rawValue; submit(found[0].rawValue); window.setTimeout(() => { last = ""; }, 3000); }
        }, 400);
      } catch { setResult({ ok: false, text: "Could not use the camera. Allow camera access, or type the code instead." }); setCamera(false); }
    })();
    return () => { stopped = true; window.clearInterval(timer); stream?.getTracks().forEach((t) => t.stop()); };
  }, [camera, submit]);

  const open = events.filter((e) => !e.cancelled);

  return (
    <div className="max-w-2xl space-y-5">
      <Notice tone="info">Ask the student to open their pass in My passes, then scan the QR code or type the code under it.</Notice>
      <div className="card space-y-4 p-6">
        <label className="block"><span className="mb-1.5 block text-sm font-semibold">Where are you checking people in?</span>
          <select className="field" value={where} onChange={(e) => { setWhere(e.target.value); setResult(null); }}>
            <option value="entrance">Fest entrance</option>
            {open.map((e) => <option key={e.id} value={e.id}>Event: {e.title}</option>)}
          </select>
        </label>
        <form onSubmit={(e) => { e.preventDefault(); submit(code); }} className="flex flex-wrap gap-2">
          <input ref={input} autoFocus className="field min-w-0 flex-1" placeholder="Pass code" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" spellCheck={false} />
          <Button type="submit" disabled={busy || code.trim().length < 8}>{where === "entrance" ? "Let in" : "Mark present"}</Button>
          {where === "entrance" && <Button type="button" variant="outline" disabled={busy || code.trim().length < 8} onClick={() => submit(code, true)}>Look up</Button>}
        </form>
        {cameraSupported && <Button variant="outline" onClick={() => setCamera((c) => !c)}><Camera className="h-4 w-4" /> {camera ? "Stop camera" : "Scan with camera"}</Button>}
        {camera && <video ref={video} muted playsInline className="aspect-video w-full rounded-2xl bg-black object-cover" />}
      </div>

      {result && (
        <div role="status" className={`flex items-start gap-3 rounded-2xl p-5 ${result.ok ? "bg-mint text-emerald-900" : "bg-red-50 text-red-800"}`}>
          {result.ok ? <CheckCircle2 className="mt-0.5 h-6 w-6 shrink-0" /> : <XCircle className="mt-0.5 h-6 w-6 shrink-0" />}
          <div className="min-w-0"><p className="text-lg font-semibold">{result.text}</p>{result.sub && <p className="text-sm opacity-80">{result.sub}</p>}</div>
        </div>
      )}

      {log.length > 0 && (
        <div className="card p-6">
          <h3 className="mb-3 font-display text-lg font-semibold">Just checked in</h3>
          <ul className="divide-y divide-black/5">{log.map((r, i) => <li key={i} className="flex items-center justify-between gap-3 py-2.5 text-sm"><span className="min-w-0 truncate font-medium">{r.text}</span>{r.undoable && r.code && <button onClick={() => undo(r.code!)} className="shrink-0 font-semibold text-red-600 hover:underline">Undo</button>}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
