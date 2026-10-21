"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AdminUser, College, FestEvent } from "@/lib/types";
import { formatDay } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Pill, Skeleton } from "@/components/ui/bits";

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
  const [people, setPeople] = useState<AdminUser[] | null>(null);
  const [query, setQuery] = useState("");
  const [events, setEvents] = useState<FestEvent[]>([]);
  const [colleges, setColleges] = useState<College[]>([]);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [area, setArea] = useState("");

  const load = useCallback(async () => {
    try {
      const [r, e, c] = await Promise.all([
        api<AdminUser[]>(`/api/admin/users?q=${encodeURIComponent(query.trim())}`),
        api<FestEvent[]>("/api/admin/events/pending"),
        api<College[]>("/api/colleges/"),
      ]);
      setPeople(r); setEvents(e); setColleges(c);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load."); setPeople([]); }
  }, [query]);
  useEffect(() => {
    if (user?.role !== "admin") return;
    const t = setTimeout(load, query ? 250 : 0);
    return () => clearTimeout(t);
  }, [user, load, query]);

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

      {people === null ? <Skeleton className="h-40" /> : (
        <>
          <Section title="People">
            <p className="mb-4 text-mute">Find an account to make it an organiser. Organisers can create fests and manage them. Accounts start as normal members.</p>
            <input className="field mb-4" placeholder="Search by name or email" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search people" />
            {people.length === 0 ? <EmptyState title="No one found" body="Try a different name or email." /> : (
              <div className="space-y-3">
                {people.map((p) => (
                  <div key={p.id} className="card flex flex-wrap items-center justify-between gap-3 p-5">
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{p.name}</p>
                      <p className="truncate text-sm text-mute">{p.email}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <Pill tone={p.role === "user" ? "neutral" : "amber"}>{p.role === "organizer" ? "Organiser" : p.role === "admin" ? "Admin" : "Member"}</Pill>
                      {p.role === "user" && <Button size="sm" onClick={() => act(`/api/admin/users/${p.id}/role`, "POST", { role: "organizer" })}>Make organiser</Button>}
                      {p.role === "organizer" && p.id !== user?.id && <Button size="sm" variant="outline" onClick={() => act(`/api/admin/users/${p.id}/role`, "POST", { role: "user" })}>Remove organiser</Button>}
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
