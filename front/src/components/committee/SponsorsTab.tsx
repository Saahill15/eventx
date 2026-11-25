"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Plus } from "lucide-react";
import { api, mediaSrc } from "@/lib/api";
import type { Sponsor } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Notice, Pill, Skeleton } from "@/components/ui/bits";
import { ImageUpload } from "@/components/ui/ImageUpload";

/** The usual kinds of sponsor. Each sets how big the logo is shown. "Something else" lets the fest use its own wording. */
const KINDS: { label: string; level: 1 | 2 | 3 | 4 }[] = [
  { label: "Title Sponsor", level: 1 }, { label: "Powered by", level: 2 }, { label: "Associate Sponsors", level: 3 },
  { label: "Gift Partner", level: 4 }, { label: "Food Partner", level: 4 }, { label: "Media Partner", level: 4 },
  { label: "Knowledge Partner", level: 4 }, { label: "Hospitality Partner", level: 4 }, { label: "Travel Partner", level: 4 },
];
const SIZES: Record<number, string> = { 1: "Largest (one or two at the top)", 2: "Large", 3: "Medium", 4: "Small (a row of partners)" };
const OTHER = "__other";

function SponsorForm({ slug, sponsor, onDone }: { slug: string; sponsor: Sponsor | null; onDone: (changed: boolean) => void }) {
  const known = sponsor ? KINDS.find((k) => k.label === sponsor.tier_label && k.level === sponsor.level) : KINDS[0];
  const [name, setName] = useState(sponsor?.name ?? "");
  const [kind, setKind] = useState(sponsor ? (known ? known.label : OTHER) : KINDS[0].label);
  const [custom, setCustom] = useState(sponsor && !known ? sponsor.tier_label : "");
  const [level, setLevel] = useState<number>(sponsor?.level ?? 3);
  const [logo, setLogo] = useState<string | null>(sponsor?.logo_url ?? null);
  const [site, setSite] = useState(sponsor?.website_url ?? "");
  const [blurb, setBlurb] = useState(sponsor?.blurb ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    const preset = KINDS.find((k) => k.label === kind);
    const body = {
      name: name.trim(), level: preset ? preset.level : level, tier_label: preset ? preset.label : custom.trim() || null,
      logo_url: logo, website_url: site.trim() || null, blurb: blurb.trim() || null,
    };
    try {
      await api(sponsor ? `/api/fests/${slug}/sponsors/${sponsor.id}` : `/api/fests/${slug}/sponsors`, { method: sponsor ? "PATCH" : "POST", body });
      onDone(true);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save the sponsor."); setBusy(false); }
  };

  return (
    <form onSubmit={save} className="card max-w-3xl space-y-5 p-6 sm:p-8">
      <h2 className="font-display text-xl font-bold tracking-tight">{sponsor ? "Edit sponsor" : "Add a sponsor"}</h2>
      <ErrorNote>{error}</ErrorNote>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name"><input className="field" required autoFocus maxLength={120} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Acme Bank" /></Field>
        <Field label="What are they to your fest?" hint="Decides where and how big their logo is shown.">
          <select className="field" value={kind} onChange={(e) => setKind(e.target.value)}>
            {KINDS.map((k) => <option key={k.label} value={k.label}>{k.label}</option>)}
            <option value={OTHER}>Something else…</option>
          </select>
        </Field>
      </div>
      {kind === OTHER && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Your wording" hint="Shown above their logo, such as “Refreshment Partner”."><input className="field" required maxLength={60} value={custom} onChange={(e) => setCustom(e.target.value)} /></Field>
          <Field label="Logo size"><select className="field" value={level} onChange={(e) => setLevel(Number(e.target.value))}>{[1, 2, 3, 4].map((l) => <option key={l} value={l}>{SIZES[l]}</option>)}</select></Field>
        </div>
      )}
      <ImageUpload kind="sponsor" value={logo} onChange={setLogo} maxWidthClass="max-w-xs" />
      <p className="-mt-2 text-xs text-mute">No logo yet? You can add the sponsor now. Their name is shown in its place until you add one.</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Their website" hint="Optional. The logo links to it."><input className="field" type="url" value={site} onChange={(e) => setSite(e.target.value)} placeholder="https://" /></Field>
        <Field label="A line about them" hint="Optional. Shown for title and “powered by” sponsors."><input className="field" maxLength={200} value={blurb} onChange={(e) => setBlurb(e.target.value)} placeholder="e.g. Our banking partner since 2019" /></Field>
      </div>
      <div className="flex gap-2"><Button type="submit" disabled={busy || !name.trim()}>{busy ? "Saving…" : sponsor ? "Save sponsor" : "Add sponsor"}</Button><Button type="button" variant="ghost" onClick={() => onDone(false)}>Cancel</Button></div>
    </form>
  );
}

/** The fest's sponsors and partners: add them with logos and a tier, put them in order. They show on the public fest page. */
export function SponsorsTab({ slug, live }: { slug: string; live: boolean }) {
  const [list, setList] = useState<Sponsor[] | null>(null);
  const [editing, setEditing] = useState<Sponsor | "new" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => { api<Sponsor[]>(`/api/fests/${slug}/sponsors`).then(setList).catch((e) => { setError(e instanceof Error ? e.message : "Could not load the sponsors."); setList([]); }); }, [slug]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => { setBusy(true); setError(""); try { await fn(); load(); } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); } setBusy(false); };

  if (list === null) return <Skeleton className="h-40" />;
  if (editing) return <SponsorForm slug={slug} sponsor={editing === "new" ? null : editing} onDone={(c) => { setEditing(null); if (c) load(); }} />;

  const groups: { key: string; label: string; items: Sponsor[] }[] = [];
  for (const s of list) {
    const key = `${s.level}|${s.tier_label.toLowerCase()}`;
    const g = groups.find((x) => x.key === key);
    if (g) g.items.push(s); else groups.push({ key, label: s.tier_label, items: [s] });
  }
  const tierMates = (s: Sponsor) => list.filter((x) => x.level === s.level);

  return (
    <div className="max-w-4xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-mute">{list.length} sponsor{list.length === 1 ? "" : "s"}. They show on your public fest page, biggest tier first.</p>
        <Button size="sm" onClick={() => setEditing("new")}><Plus className="h-4 w-4" /> Add a sponsor</Button>
      </div>
      {!live && list.length > 0 && <Notice tone="info">Sponsors appear on the public page once your fest is live.</Notice>}
      <ErrorNote>{error}</ErrorNote>

      {list.length === 0 ? (
        <EmptyState title="No sponsors yet" body="Add your title sponsor, your partners and the brands backing your fest. Their logos get their own section on your fest page." action={<Button onClick={() => setEditing("new")}>Add the first sponsor</Button>} />
      ) : groups.map((g) => (
        <section key={g.key} aria-label={g.label} className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-mute">{g.label}</p>
          {g.items.map((s) => {
            const mates = tierMates(s); const i = mates.findIndex((x) => x.id === s.id);
            const logo = mediaSrc(s.logo_url);
            return (
              <div key={s.id} className="card flex flex-wrap items-center gap-4 p-4">
                <div className="flex h-14 w-24 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-wash">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  {logo ? <img src={logo} alt="" className="h-full w-full object-contain p-1" /> : <span className="px-1 text-center text-[11px] font-semibold text-mute">No logo</span>}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 font-semibold">{s.name}{!s.logo_url && <Pill tone="amber">Needs a logo</Pill>}</p>
                  <p className="truncate text-sm text-mute">{[s.blurb, s.website_url?.replace(/^https?:\/\//, "")].filter(Boolean).join(" · ") || "No website or line yet"}</p>
                </div>
                <div className="flex items-center gap-1">
                  <button aria-label={`Move ${s.name} up`} disabled={busy || i === 0} onClick={() => act(() => api(`/api/fests/${slug}/sponsors/${s.id}/move`, { method: "POST", body: { direction: "up" } }))} className="rounded-full p-2 hover:bg-wash disabled:opacity-30"><ArrowUp className="h-4 w-4" /></button>
                  <button aria-label={`Move ${s.name} down`} disabled={busy || i === mates.length - 1} onClick={() => act(() => api(`/api/fests/${slug}/sponsors/${s.id}/move`, { method: "POST", body: { direction: "down" } }))} className="rounded-full p-2 hover:bg-wash disabled:opacity-30"><ArrowDown className="h-4 w-4" /></button>
                  <Button size="sm" variant="outline" onClick={() => setEditing(s)}>Edit</Button>
                  <button disabled={busy} onClick={() => window.confirm(`Remove ${s.name} from your sponsors?`) && act(() => api(`/api/fests/${slug}/sponsors/${s.id}`, { method: "DELETE" }))} className="px-2 text-sm font-semibold text-red-600 hover:underline">Remove</button>
                </div>
              </div>
            );
          })}
        </section>
      ))}
    </div>
  );
}
