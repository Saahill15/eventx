"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Lock } from "lucide-react";
import { SITE_URL, api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/bits";

interface Link { name: string | null; path: string | null; target_path: string; enabled: boolean }
interface Check { available: boolean; reason: "invalid" | "reserved" | "taken" | null }

const HOST = (() => { try { return new URL(SITE_URL).host; } catch { return "hiveout.in"; } })();
const WHY = { invalid: "Use 3 to 40 lowercase letters, numbers and single hyphens.", reserved: "That name is used by the site itself.", taken: "That name is already taken." } as const;

/** A short custom address for a fest, such as hiveout.in/mood-indigo. Built to work for events as well later. */
export function ShortLinkCard({ slug, live }: { slug: string; live: boolean }) {
  const [link, setLink] = useState<Link | null>(null);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [result, setResult] = useState<Check | null>(null);
  const [checking, setChecking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { api<Link>(`/api/short-links/fests/${slug}`).then(setLink).catch((e) => setError(e instanceof Error ? e.message : "Could not load.")); }, [slug]);

  // Check the name shortly after the person stops typing
  useEffect(() => {
    const n = name.trim().toLowerCase();
    setResult(null);
    if (!editing || n.length < 3) return;
    setChecking(true);
    const t = setTimeout(() => {
      api<Check>(`/api/short-links/check?name=${encodeURIComponent(n)}&fest=${encodeURIComponent(slug)}`).then(setResult).catch((e) => setError(e instanceof Error ? e.message : "Could not check.")).finally(() => setChecking(false));
    }, 350);
    return () => { clearTimeout(t); setChecking(false); };
  }, [name, editing, slug]);

  if (!link) return error ? <ErrorNote>{error}</ErrorNote> : null;

  const full = link.name ? `${HOST}/${link.name}` : null;
  const save = async () => {
    setBusy(true); setError("");
    try { setLink(await api<Link>(`/api/short-links/fests/${slug}`, { method: "PUT", body: { name: name.trim() } })); setEditing(false); setName(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not claim that name."); }
    setBusy(false);
  };
  const release = async () => {
    if (!window.confirm(`Give up ${full}? Anyone using it will get "not found", and someone else could take it.`)) return;
    setBusy(true); setError("");
    try { setLink(await api<Link>(`/api/short-links/fests/${slug}`, { method: "DELETE" })); } catch (e) { setError(e instanceof Error ? e.message : "Could not release it."); }
    setBusy(false);
  };
  const copy = async () => { try { await navigator.clipboard.writeText(`${window.location.protocol}//${full}`); setCopied(true); setTimeout(() => setCopied(false), 1800); } catch { /* clipboard blocked */ } };

  return (
    <section className="card space-y-4 p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-lg font-semibold tracking-tight">Your own short link</h3>
          <p className="mt-1 text-sm text-mute">A short address that is easy to share, like {HOST}/your-fest. It opens your fest page{live ? "." : " once the fest is live."}</p>
        </div>
        {!link.enabled && <span className="flex shrink-0 items-center gap-1.5 rounded-full bg-wash px-3 py-1 text-xs font-semibold text-mute"><Lock className="h-3.5 w-3.5" /> Paid plan</span>}
      </div>
      <ErrorNote>{error}</ErrorNote>

      {!link.enabled ? (
        <p className="rounded-2xl bg-wash px-4 py-3 text-sm text-neutral-700">Custom short links are part of a paid plan{full ? `. Your current link, ${full}, keeps working.` : "."}</p>
      ) : link.name && !editing ? (
        <div className="flex flex-wrap items-center gap-3">
          <p className="rounded-full bg-wash px-4 py-2 font-semibold">{full}</p>
          <Button size="sm" variant="outline" onClick={copy}>{copied ? <><Check className="h-4 w-4" /> Copied</> : <><Copy className="h-4 w-4" /> Copy</>}</Button>
          <Button size="sm" variant="outline" onClick={() => { setEditing(true); setName(link.name ?? ""); }}>Change</Button>
          <button disabled={busy} onClick={release} className="px-2 text-sm font-semibold text-red-600 hover:underline">Remove</button>
        </div>
      ) : editing || !link.name ? (
        <div className="space-y-3">
          {!editing && <Button onClick={() => setEditing(true)}>Claim a short link</Button>}
          {editing && (
            <>
              <div className="flex max-w-xl items-center overflow-hidden rounded-[0.9rem] border border-black/10 bg-white focus-within:border-brand focus-within:shadow-[0_0_0_4px_rgba(245,163,0,0.35)]">
                <span className="select-none border-r border-black/10 bg-wash px-4 py-3 text-sm text-mute">{HOST}/</span>
                <input autoFocus className="min-w-0 flex-1 bg-transparent px-4 py-3 text-[0.95rem] outline-none" placeholder="your-fest" maxLength={40} value={name} onChange={(e) => setName(e.target.value.toLowerCase().replace(/\s+/g, "-"))} aria-label="Short link name" />
              </div>
              <p role="status" className={`min-h-5 text-sm ${result?.available ? "font-semibold text-emerald-700" : "text-red-700"}`}>
                {name.trim().length > 0 && name.trim().length < 3 ? "At least 3 characters." : checking ? <span className="text-mute">Checking…</span> : result ? (result.available ? `${HOST}/${name.trim()} is yours to take.` : result.reason ? WHY[result.reason] : "") : ""}
              </p>
              <div className="flex gap-2">
                <Button size="sm" disabled={busy || !result?.available || name.trim() === link.name} onClick={save}>{busy ? "Saving…" : link.name ? "Save the new link" : "Claim this link"}</Button>
                <Button size="sm" variant="ghost" onClick={() => { setEditing(false); setName(""); }}>Cancel</Button>
              </div>
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}
