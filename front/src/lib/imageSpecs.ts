/**
 * The pictures a fest uploads, and what each should look like. The upload box shows these, the cropper locks to the shape,
 * and the result is sized to fit, so nobody has to open an image editor first.
 */
export type ImageKind = "banner" | "logo" | "cover" | "sponsor";

export interface ImageSpec {
  label: string;
  /** width divided by height */
  ratio: number;
  /** the size the saved picture is cut down to, in pixels */
  width: number;
  height: number;
  /** below this the picture will look soft on a big screen */
  minWidth: number;
  minHeight: number;
  shape: string;
  where: string;
}

export const IMAGE_SPECS: Record<ImageKind, ImageSpec> = {
  banner: { label: "Banner", ratio: 1920 / 820, width: 1920, height: 820, minWidth: 1200, minHeight: 512, shape: "wide", where: "the top of your fest page and on fest cards" },
  logo: { label: "Logo", ratio: 1, width: 512, height: 512, minWidth: 256, minHeight: 256, shape: "square", where: "next to your fest's name" },
  sponsor: { label: "Sponsor logo", ratio: 3 / 2, width: 600, height: 400, minWidth: 300, minHeight: 200, shape: "wide, with some space round the logo", where: "the sponsors section of your fest page" },
  cover: { label: "Cover image", ratio: 1280 / 800, width: 1280, height: 800, minWidth: 800, minHeight: 500, shape: "landscape", where: "the event's card and page" },
};

/** The biggest file the server takes, and the biggest original we accept (we shrink it before sending). */
export const MAX_UPLOAD_BYTES = 3 * 1024 * 1024;
export const MAX_ORIGINAL_BYTES = 15 * 1024 * 1024;
export const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];

export const specLine = (s: ImageSpec) => `${s.width} × ${s.height} px (${s.shape})`;

const load = (src: string) => new Promise<HTMLImageElement>((resolve, reject) => {
  const img = new Image();
  img.onload = () => resolve(img);
  img.onerror = () => reject(new Error("That file could not be read as an image."));
  img.src = src;
});

export async function imageSize(src: string): Promise<{ width: number; height: number }> {
  const img = await load(src);
  return { width: img.naturalWidth, height: img.naturalHeight };
}

export interface CropArea { x: number; y: number; width: number; height: number }

/** Cut the chosen area out of the picture, scale it down to the spec if it is bigger, and keep it under the server's size limit. */
export async function cropToFile(src: string, area: CropArea, spec: ImageSpec, name: string, keepTransparency: boolean): Promise<File> {
  const img = await load(src);
  const mime = keepTransparency ? "image/png" : "image/jpeg";
  let scale = Math.min(1, spec.width / area.width);
  for (let attempt = 0; attempt < 6; attempt++) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(area.width * scale));
    canvas.height = Math.max(1, Math.round(area.height * scale));
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("This browser cannot crop images.");
    if (!keepTransparency) { ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, canvas.width, canvas.height); }
    ctx.drawImage(img, area.x, area.y, area.width, area.height, 0, 0, canvas.width, canvas.height);
    for (const quality of [0.92, 0.82, 0.7, 0.55]) {
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, mime, keepTransparency ? undefined : quality));
      if (blob && blob.size <= MAX_UPLOAD_BYTES) return new File([blob], name.replace(/\.[^.]+$/, "") + (keepTransparency ? ".png" : ".jpg"), { type: mime });
      if (keepTransparency) break; // PNG has no quality setting, so go straight to a smaller size
    }
    scale *= 0.75;
  }
  throw new Error("Could not make that picture small enough. Try a simpler image.");
}
