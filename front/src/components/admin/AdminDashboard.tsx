"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { College, FestEvent, OrganizerRequestRow } from "@/lib/types";
import { formatDay } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Skeleton } from "@/components/ui/bits";

function Section({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <section className="mb-12">
      <h2 className="mb-4 font-display text-xl font-extrabold tracking-tight">{title}{count !== undefined && <span className="ml-2 text-base font-semibold text-neutral-400">{count}</span>}</h2>
      {children}
    </section>
  );
}

export function AdminDashboard() {
  const { user } = useAuth();
  const [requests, setRequests] = useState<OrganizerRequestRow[] | null>(null);
  const [events, setEvents] = useState<FestEvent[]>([]);
  const [colleges, setColleges] = useState<College[]>([]);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [area, setArea] = useState("");

  const load = useCallback(async () => {
    try {
      const [r, e, c] = await Promise.all([
        api<OrganizerRequestRow[]>("/api/admin/organizer-requests"),
        api<FestEvent[]>("/api/admin/events/pending"),
        api<College[]>("/api/colleges/"),
      ]);
      setRequests(r); setEvents(e); setColleges(c);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load."); setRequests([]); }
  }, []);
  useEffect(() => { if (user?.role === "admin") load(); }, [user, load]);

  const act = async (path: string, method = "POST", body?: unknown) => {
    setError("");
    try { await api(path, { method, body }); } catch (err) { setError(err instanceof Error ? err.message : "That action failed."); }
    load();
  };

  if (user && user.role !== "admin") {
    return <div className="mx-auto max-w-md px-6 py-20 text-center"><p className="text-neutral-500">This page is for HiveOut admins.</p><Button href="/" className="mt-6" variant="outline">Back to home</Button></div>;
  }

  return (
    <div className="mx-auto max-w-4xl px-6 pb-8 pt-8">
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-chip-ink">Admin</p>
      <h1 className="mb-8 mt-1 font-display text-4xl font-bold tracking-tight sm:text-5xl">Admin dashboard</h1>
      <div className="mb-6"><ErrorNote>{error}</ErrorNote></div>

      {requests === null ? <Skeleton className="h-40" /> : (
        <>
          <Section title="Organiser requests" count={requests.length}>
            {requests.length === 0 ? <EmptyState title="No pending requests" /> : (
              <div className="space-y-3">
                {requests.map((r) => (
                  <div key={r.id} className="bg-white ring-1 ring-black/5 shadow-[var(--shadow-card)] flex flex-wrap items-center justify-between gap-3 rounded-3xl p-5">
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{r.user_name ?? `User #${r.user_id}`}</p>
                      <p className="truncate text-sm text-neutral-500">{r.user_email} · asked {new Date(r.requested_at).toLocaleDateString("en-IN")}</p>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => act(`/api/admin/organizer-requests/${r.id}/approve`)}>Approve</Button>
                      <Button size="sm" variant="outline" onClick={() => act(`/api/admin/organizer-requests/${r.id}/reject`)}>Reject</Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Section>

          <Section title="Pending city events" count={events.length}>
            {events.length === 0 ? <EmptyState title="No pending events" body="Fest events publish directly. Only standalone city events wait for review." /> : (
              <div className="space-y-3">
                {events.map((e) => (
                  <div key={e.id} className="bg-white ring-1 ring-black/5 shadow-[var(--shadow-card)] flex flex-wrap items-center justify-between gap-3 rounded-3xl p-5">
                    <div className="min-w-0">
                      <p className="font-semibold">{e.title}</p>
                      <p className="text-sm text-neutral-500">{formatDay(e.date)}{e.location ? ` · ${e.location}` : ""}</p>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => act(`/api/admin/events/${e.id}/approve`)}>Approve</Button>
                      <Button size="sm" variant="outline" onClick={() => act(`/api/admin/events/${e.id}/reject`)}>Reject</Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Section>

          <Section title="Colleges" count={colleges.length}>
            <form
              onSubmit={async (e) => { e.preventDefault(); await act("/api/colleges/", "POST", { name, area: area || null }); setName(""); setArea(""); }}
              className="bg-white ring-1 ring-black/5 shadow-[var(--shadow-card)] mb-4 grid gap-3 rounded-3xl p-5 sm:grid-cols-[1fr_1fr_auto]"
            >
              <input className="field" required placeholder="College name" value={name} onChange={(e) => setName(e.target.value)} />
              <input className="field" placeholder="Area (optional)" value={area} onChange={(e) => setArea(e.target.value)} />
              <Button type="submit">Add</Button>
            </form>
            <div className="grid gap-3 sm:grid-cols-2">
              {colleges.map((c) => (
                <div key={c.id} className="bg-white ring-1 ring-black/5 shadow-[var(--shadow-card)] flex items-center justify-between gap-3 rounded-2xl p-4">
                  <div className="min-w-0"><p className="truncate font-semibold">{c.name}</p>{c.area && <p className="truncate text-xs text-neutral-500">{c.area}</p>}</div>
                  <button onClick={() => window.confirm(`Delete ${c.name}?`) && act(`/api/colleges/${c.id}`, "DELETE")} className="text-sm font-semibold text-red-600 hover:underline">Delete</button>
                </div>
              ))}
            </div>
          </Section>
        </>
      )}
    </div>
  );
}
