import type { Leaderboard as Board } from "@/lib/types";

const MEDAL = ["bg-amber-200 text-amber-900", "bg-neutral-200 text-neutral-800", "bg-orange-200 text-orange-900"];
const badge = (rank: number | null) => (
  <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold ${rank && rank <= 3 ? MEDAL[rank - 1] : "bg-chip text-chip-ink"}`}>{rank ?? "–"}</span>
);

/** The competition between colleges, on the public fest page: awards, college standings and contingent standings. */
export function Leaderboard({ board, festName }: { board: Board; festName: string }) {
  const awards = board.awards.filter((a) => a.winners.length > 0);
  const colleges = board.colleges.slice(0, 10);
  const contingents = board.contingents.filter((c) => !c.disqualified);
  if (awards.length === 0 && colleges.length === 0) return null;
  return (
    <section className="card space-y-9 p-8 sm:p-10" aria-label="Leaderboard">
      <div>
        <h2 className="font-display text-3xl font-semibold tracking-tight">Leaderboard</h2>
        <p className="mt-2 text-mute">How the colleges are doing at {festName}{board.ranking_basis === "events" ? ", counting what each earned in events" : ""}.</p>
      </div>

      {awards.length > 0 && (
        <div>
          <p className="mb-4 text-xs font-bold uppercase tracking-[0.18em] text-chip-ink">Awards</p>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {awards.map((a) => (
              <li key={a.id} className="rounded-3xl bg-tint p-5"><p className="text-sm font-semibold text-tint-ink">{a.title}</p><p className="mt-1 font-display text-xl font-semibold leading-snug">{a.winners.map((w) => w.name).join(" and ")}</p>{a.event_title && <p className="mt-1 text-sm text-mute">{a.event_title}</p>}</li>
            ))}
          </ul>
        </div>
      )}

      {colleges.length > 0 && (
        <div>
          <p className="mb-4 text-xs font-bold uppercase tracking-[0.18em] text-chip-ink">Colleges</p>
          <ol className="space-y-2">
            {colleges.map((c) => (
              <li key={c.college_name} className="flex items-center gap-4 rounded-2xl bg-wash px-4 py-3">{badge(c.rank)}<div className="min-w-0 flex-1"><p className="truncate font-semibold">{c.college_name}</p>{c.contingents > 1 && <p className="truncate text-sm text-mute">{c.contingents} contingents together</p>}</div><p className="font-display text-xl font-semibold">{c.score}</p></li>
            ))}
          </ol>
        </div>
      )}

      {contingents.length > 1 && (
        <div>
          <p className="mb-4 text-xs font-bold uppercase tracking-[0.18em] text-chip-ink">Contingents</p>
          <ol className="grid gap-2 sm:grid-cols-2">
            {contingents.slice(0, 20).map((c) => (
              <li key={c.contingent_id} className="flex items-center gap-3 rounded-2xl bg-wash px-4 py-3">{badge(c.rank)}<div className="min-w-0 flex-1"><p className="truncate font-semibold">{c.name ?? c.college_name}{c.code && <span className="ml-2 text-xs font-normal text-mute">{c.code}</span>}</p>{c.name && <p className="truncate text-sm text-mute">{c.college_name}</p>}</div><p className="font-semibold">{c.score}</p></li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
