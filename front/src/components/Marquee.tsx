/** Endless slow-scrolling strip. Pauses on hover. */
export function Marquee({ items }: { items: string[] }) {
  const row = [...items, ...items];
  return (
    <div className="marquee relative overflow-hidden" aria-hidden>
      <div className="marquee-track flex w-max gap-4">
        {row.map((t, i) => <span key={i} className="whitespace-nowrap rounded-full bg-wash px-6 py-3 font-display text-lg font-semibold">{t}</span>)}
      </div>
    </div>
  );
}
