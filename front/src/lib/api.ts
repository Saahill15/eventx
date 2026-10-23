import type { College, Fest, FestEvent } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/** Turn an API error body into one readable sentence. FastAPI sends a string, or a list for validation errors. */
function messageFrom(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail) return detail;
  // Some errors carry a headline and a list, e.g. what a fest is still missing
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as { message?: string; missing?: string[] };
    if (d.message) return d.missing?.length ? `${d.message}: ${d.missing.join("; ")}` : d.message;
  }
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = Array.isArray(d.loc) ? String(d.loc[d.loc.length - 1]) : "";
        return field && field !== "body" ? `${field}: ${d.msg}` : (d.msg ?? "Invalid value");
      })
      .join("; ");
  }
  if (status === 429) return "Too many attempts. Please wait a few minutes.";
  return "Something went wrong. Please try again.";
}

/** Browser-side request. Adds the saved login token when there is one. */
export async function api<T>(path: string, options: { method?: string; body?: unknown; token?: string | null } = {}): Promise<T> {
  const token = options.token ?? (typeof window !== "undefined" ? window.localStorage.getItem("token") : null);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: options.method ?? "GET",
      headers: {
        ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection and try again.", 0);
  }
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && token && typeof window !== "undefined" && !path.startsWith("/api/auth/")) {
      window.dispatchEvent(new Event("auth:expired"));
    }
    throw new ApiError(messageFrom(res.status, body), res.status);
  }
  return body as T;
}

/**
 * Server-side read of public data. Returns null when the API is down so pages can show a friendly state.
 * Pass revalidate = 0 for a single fest or event: when one is taken offline the API answers 404, and a saved copy that only
 * refreshes on success would keep showing it. Lists are fine to keep for a short while, since they simply get shorter.
 */
async function publicGet<T>(path: string, revalidate = 30): Promise<T | null> {
  try {
    const res = await fetch(`${API_URL}${path}`, revalidate === 0 ? { cache: "no-store" } : { next: { revalidate } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export const getLiveFests = () => publicGet<Fest[]>("/api/fests/");
export const getFestBySlug = (slug: string) => publicGet<Fest>(`/api/fests/${encodeURIComponent(slug)}`, 0);
export const getFestEvents = (slug: string) => publicGet<FestEvent[]>(`/api/fests/${encodeURIComponent(slug)}/events`, 0);
export const getAllEvents = () => publicGet<FestEvent[]>("/api/events/");
export const getCityEvents = () => publicGet<FestEvent[]>("/api/events/city");
export const getEventById = (id: string) => publicGet<FestEvent>(`/api/events/${encodeURIComponent(id)}`, 0);
export const getColleges = () => publicGet<College[]>("/api/colleges/", 120);

/** Download a file (such as a CSV) from a protected endpoint and hand it to the browser as a save-as. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const token = window.localStorage.getItem("token");
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection and try again.", 0);
  }
  if (!res.ok) throw new ApiError("Could not download the file.", res.status);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Open a protected file (such as an uploaded document) in a new tab. */
export async function openFile(path: string): Promise<void> {
  const token = window.localStorage.getItem("token");
  const win = window.open("", "_blank");
  try {
    const res = await fetch(`${API_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!res.ok) throw new ApiError("Could not open the file.", res.status);
    const url = URL.createObjectURL(await res.blob());
    if (win) win.location.href = url; else window.location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (err) {
    win?.close();
    throw err;
  }
}

/** Uploaded images come back as /api/media/<id>, which lives on the API server, not on this site. */
export const mediaSrc = (url: string | null | undefined): string | null => (url ? (url.startsWith("/api/media/") ? `${API_URL}${url}` : url) : null);

/** Send a file (multipart) to a protected endpoint and read the JSON answer. */
export async function postFile<T>(path: string, file: File): Promise<T> {
  const token = window.localStorage.getItem("token");
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method: "POST", body: form, headers: token ? { Authorization: `Bearer ${token}` } : {} });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection and try again.", 0);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(messageFrom(res.status, body), res.status);
  return body as T;
}

/** Upload a JPEG, PNG or WebP (up to 3 MB) and get back the address to store on a fest or event. */
export async function uploadImage(file: File): Promise<string> {
  const token = window.localStorage.getItem("token");
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/media`, { method: "POST", body: form, headers: token ? { Authorization: `Bearer ${token}` } : {} });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection and try again.", 0);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(messageFrom(res.status, body), res.status);
  return (body as { url: string }).url;
}

/** Where a custom short name (hiveout.in/name) leads, or null when it is unknown or the fest is not public. */
export async function resolveShortLink(name: string): Promise<string | null> {
  try {
    const res = await fetch(`${API_URL}/api/short-links/resolve/${encodeURIComponent(name)}`, { cache: "no-store" });
    return res.ok ? ((await res.json()) as { path: string }).path : null;
  } catch {
    return null;
  }
}
