"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Cropper from "react-easy-crop";
import { Button } from "./Button";
import type { CropArea, ImageSpec } from "@/lib/imageSpecs";
import { specLine } from "@/lib/imageSpecs";

/**
 * Crop a chosen picture to the shape the page needs. Drag to move, slide to zoom. Nothing is uploaded until "Use this crop".
 */
export function ImageCropper({ src, spec, size, busy, onCancel, onDone }: {
  src: string; spec: ImageSpec; size: { width: number; height: number } | null; busy: boolean; onCancel: () => void; onDone: (area: CropArea) => void;
}) {
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const area = useRef<CropArea | null>(null);
  const confirm = useRef<HTMLButtonElement>(null);
  const small = !!size && (size.width < spec.minWidth || size.height < spec.minHeight);

  const onComplete = useCallback((_: unknown, pixels: CropArea) => { area.current = pixels; }, []);

  useEffect(() => {
    confirm.current?.focus();
    const key = (e: KeyboardEvent) => { if (e.key === "Escape" && !busy) onCancel(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [busy, onCancel]);

  return (
    <div role="dialog" aria-modal="true" aria-label={`Crop your ${spec.label.toLowerCase()}`} className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="card flex max-h-[95vh] w-full max-w-2xl flex-col gap-4 overflow-y-auto p-5 shadow-[var(--shadow-pop)] sm:p-6">
        <div>
          <h2 className="font-display text-xl font-bold tracking-tight">Crop your {spec.label.toLowerCase()}</h2>
          <p className="mt-1 text-sm text-mute">It shows at {specLine(spec)}, on {spec.where}. Drag the picture to move it and use the slider to zoom.</p>
        </div>
        <div className="relative h-[min(52vh,26rem)] w-full overflow-hidden rounded-2xl bg-neutral-900">
          <Cropper image={src} crop={crop} zoom={zoom} aspect={spec.ratio} onCropChange={setCrop} onZoomChange={setZoom} onCropComplete={onComplete} showGrid />
        </div>
        <label className="flex items-center gap-3 text-sm font-medium">
          <span className="w-12 shrink-0 text-mute">Zoom</span>
          <input type="range" min={1} max={4} step={0.02} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} className="w-full accent-[#111]" aria-label="Zoom" />
        </label>
        {small && size && <p role="alert" className="rounded-2xl bg-tint px-4 py-3 text-sm text-tint-ink">This picture is {size.width} × {size.height} px, a bit small for a {spec.label.toLowerCase()}. It may look blurry on big screens. A picture at least {spec.minWidth} px wide works best.</p>}
        <div className="flex flex-wrap justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onCancel} disabled={busy}>Cancel</Button>
          <button ref={confirm} type="button" disabled={busy} onClick={() => area.current && onDone(area.current)} className="inline-flex h-11 items-center justify-center rounded-full bg-ink px-6 text-[0.9375rem] font-semibold text-white transition hover:bg-neutral-700 disabled:opacity-50">{busy ? "Uploading…" : "Use this crop"}</button>
        </div>
      </div>
    </div>
  );
}
