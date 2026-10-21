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

/** Server-side read of public data. Returns null when the API is down so pages can show a friendly state. */
async function publicGet<T>(path: string, revalidate = 30): Promise<T | null> {
  try {
    const res = await fetch(`${API_URL}${path}`, { next: { revalidate } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export const getLiveFests = () => publicGet<Fest[]>("/api/fests/");
export const getFestBySlug = (slug: string) => publicGet<Fest>(`/api/fests/${encodeURIComponent(slug)}`);
export const getFestEvents = (slug: string) => publicGet<FestEvent[]>(`/api/fests/${encodeURIComponent(slug)}/events`);
export const getAllEvents = () => publicGet<FestEvent[]>("/api/events/");
export const getCityEvents = () => publicGet<FestEvent[]>("/api/events/city");
export const getEventById = (id: string) => publicGet<FestEvent>(`/api/events/${encodeURIComponent(id)}`);
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
