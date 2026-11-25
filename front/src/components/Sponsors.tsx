import type { Sponsor } from "@/lib/types";
import { mediaSrc } from "@/lib/api";

/** How big each tier is shown. The title sponsor gets the most room, partners the least. */
const TIER: Record<number, { grid: string; box: string; name: string; blurb: boolean }> = {
  1: { grid: "grid-cols-1 sm:grid-cols-2 lg:max-w-3xl", box: "h-32 sm:h-40", name: "text-2xl", blurb: true },
  2: { grid: "grid-cols-2 lg:grid-cols-3", box: "h-24 sm:h-28", name: "text-lg", blurb: true },
  3: { grid: "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4", box: "h-20 sm:h-24", name: "text-base", blurb: false },
  4: { grid: "grid-cols-2 sm:grid-cols-3 lg:grid-cols-5", box: "h-16 sm:h-20", name: "text-sm", blurb: false },
};

function Tile({ s }: { s: Sponsor }) {
  const t = TIER[s.level] ?? TIER[3];
  const logo = mediaSrc(s.logo_url);
  const body = (
    <>
      <div className={`flex w-full items-center justify-center rounded-2xl bg-white p-3 ring-1 ring-black/5 transition group-hover:ring-black/20 ${t.box}`}>
        {logo
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={logo} alt={s.name} loading="lazy" className="h-full w-full object-contain" />
          : <span className={`text-center font-display font-semibold leading-tight ${t.name}`}>{s.name}</span>}
      </div>
      {logo && <p className={`mt-2 text-center font-semibold leading-tight ${t.name}`}>{s.name}</p>}
      {t.blurb && s.blurb && <p className="mt-1 text-center text-sm text-mute">{s.blurb}</p>}
    </>
  );
  return s.website_url
    ? <a href={s.website_url} target="_blank" rel="noopener noreferrer sponsored" className="group block" aria-label={`${s.name} (opens their website)`}>{body}</a>
    : <div className="group block">{body}</div>;
}

/** The sponsors of a fest on its public page, grouped by tier (largest first), each tier under the fest's own label. */
export function Sponsors({ sponsors, festName }: { sponsors: Sponsor[]; festName: string }) {
  if (sponsors.length === 0) return null;
  // The list arrives sorted by tier then order. Groups keep that order, one per (tier, label)
  const groups: { key: string; level: number; label: string; items: Sponsor[] }[] = [];
  for (const s of sponsors) {
    const key = `${s.level}|${s.tier_label.toLowerCase()}`;
    const g = groups.find((x) => x.key === key);
    if (g) g.items.push(s); else groups.push({ key, level: s.level, label: s.tier_label, items: [s] });
  }
  return (
    <section className="card space-y-9 p-8 sm:p-10" aria-label="Sponsors">
      <div>
        <h2 className="font-display text-3xl font-semibold tracking-tight">Our sponsors</h2>
        <p className="mt-2 text-mute">The people and brands who make {festName} possible.</p>
      </div>
      {groups.map((g) => (
        <div key={g.key}>
          <p className="mb-4 text-xs font-bold uppercase tracking-[0.18em] text-chip-ink">{g.label}</p>
          <div className={`grid gap-4 ${(TIER[g.level] ?? TIER[3]).grid}`}>
            {g.items.map((s) => <Tile key={s.id} s={s} />)}
          </div>
        </div>
      ))}
    </section>
  );
}
