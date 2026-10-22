"use client";

import { useRef, useState } from "react";
import { ImagePlus, X } from "lucide-react";
import { mediaSrc, uploadImage } from "@/lib/api";

/** Pick an image from the computer. Shows a preview and hands back the stored address (or null when removed). */
export function ImageUpload({ value, onChange, label, aspect = "aspect-[16/9]" }: { value: string | null; onChange: (url: string | null) => void; label: string; aspect?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const pick = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true); setError("");
    try { onChange(await uploadImage(file)); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not upload that image."); }
    setBusy(false);
    if (input.current) input.current.value = "";
  };

  const src = mediaSrc(value);
  return (
    <div>
      <span className="mb-1.5 block text-sm font-semibold">{label}</span>
      <div className={`relative ${aspect} w-full max-w-md overflow-hidden rounded-2xl bg-wash ring-1 ring-black/5`}>
        {src ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={src} alt="" className="h-full w-full object-cover" />
            <button type="button" onClick={() => onChange(null)} aria-label="Remove image" className="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full bg-black/60 text-white hover:bg-black/80"><X className="h-4 w-4" /></button>
          </>
        ) : (
          <button type="button" onClick={() => input.current?.click()} disabled={busy} className="flex h-full w-full flex-col items-center justify-center gap-2 text-sm font-medium text-mute hover:text-ink">
            <ImagePlus className="h-6 w-6" />{busy ? "Uploading…" : "Choose an image"}
          </button>
        )}
      </div>
      {src && <button type="button" onClick={() => input.current?.click()} disabled={busy} className="mt-2 text-sm font-semibold underline underline-offset-4">{busy ? "Uploading…" : "Replace image"}</button>}
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
      <p className="mt-1.5 text-xs text-mute">JPEG, PNG or WebP, up to 3 MB.</p>
      {error && <p role="alert" className="mt-1 text-sm text-red-700">{error}</p>}
    </div>
  );
}
