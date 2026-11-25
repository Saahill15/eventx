"use client";

import { useEffect, useRef, useState } from "react";
import { ImagePlus, X } from "lucide-react";
import { mediaSrc, uploadImage } from "@/lib/api";
import { ACCEPTED_TYPES, IMAGE_SPECS, MAX_ORIGINAL_BYTES, cropToFile, imageSize, specLine, type CropArea, type ImageKind } from "@/lib/imageSpecs";
import { ImageCropper } from "./ImageCropper";

/**
 * Pick an image, crop it to the right shape, and upload it. The box says what size and shape is wanted before anything is chosen.
 * Big photos are fine: they are cut down to size here, so nobody has to resize anything first.
 */
export function ImageUpload({ value, onChange, label, kind, maxWidthClass = "max-w-md" }: { value: string | null; onChange: (url: string | null) => void; label?: string; kind: ImageKind; maxWidthClass?: string }) {
  const spec = IMAGE_SPECS[kind];
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [picked, setPicked] = useState<{ src: string; name: string; type: string; size: { width: number; height: number } | null } | null>(null);

  useEffect(() => () => { if (picked) URL.revokeObjectURL(picked.src); }, [picked]);

  const pick = async (file: File | undefined) => {
    if (input.current) input.current.value = "";
    if (!file) return;
    setError("");
    if (!ACCEPTED_TYPES.includes(file.type)) { setError("Use a JPEG, PNG or WebP picture."); return; }
    if (file.size > MAX_ORIGINAL_BYTES) { setError(`That file is ${(file.size / 1024 / 1024).toFixed(0)} MB. Pick one under ${MAX_ORIGINAL_BYTES / 1024 / 1024} MB.`); return; }
    const src = URL.createObjectURL(file);
    try { setPicked({ src, name: file.name, type: file.type, size: await imageSize(src) }); }
    catch (err) { URL.revokeObjectURL(src); setError(err instanceof Error ? err.message : "That file could not be read as an image."); }
  };

  const finish = async (area: CropArea) => {
    if (!picked) return;
    setBusy(true); setError("");
    try {
      const file = await cropToFile(picked.src, area, spec, picked.name, (kind === "logo" || kind === "sponsor") && picked.type === "image/png");
      onChange(await uploadImage(file));
      setPicked(null);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not upload that picture."); }
    setBusy(false);
  };

  const src = mediaSrc(value);
  const title = label ?? spec.label;
  return (
    <div>
      <span className="mb-1.5 block text-sm font-semibold">{title}</span>
      <div style={{ aspectRatio: String(spec.ratio) }} className={`relative w-full ${maxWidthClass} overflow-hidden rounded-2xl bg-wash ring-1 ring-black/5`}>
        {src ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={src} alt="" className="h-full w-full object-cover" />
            <button type="button" onClick={() => onChange(null)} aria-label={`Remove ${title.toLowerCase()}`} className="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full bg-black/60 text-white hover:bg-black/80"><X className="h-4 w-4" /></button>
          </>
        ) : (
          <button type="button" onClick={() => input.current?.click()} className="flex h-full w-full flex-col items-center justify-center gap-1.5 px-3 text-center text-sm font-medium text-mute hover:text-ink">
            <ImagePlus className="h-6 w-6" /><span>Choose a picture</span><span className="text-xs font-normal">{specLine(spec)}</span>
          </button>
        )}
      </div>
      {src && <button type="button" onClick={() => input.current?.click()} className="mt-2 text-sm font-semibold underline underline-offset-4">Replace picture</button>}
      <input ref={input} type="file" accept={ACCEPTED_TYPES.join(",")} className="hidden" aria-label={`Choose a ${title.toLowerCase()}`} onChange={(e) => pick(e.target.files?.[0])} />
      <p className="mt-1.5 text-xs text-mute">Best at {specLine(spec)}, shown on {spec.where}. JPEG, PNG or WebP. Big photos are fine: you crop it next, and we shrink it to fit.</p>
      {error && <p role="alert" className="mt-1 text-sm text-red-700">{error}</p>}
      {picked && <ImageCropper src={picked.src} spec={spec} size={picked.size} busy={busy} onCancel={() => setPicked(null)} onDone={finish} />}
    </div>
  );
}
