"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { College, Fest, MyFest } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Pill, Skeleton } from "@/components/ui/bits";
import { Field } from "@/components/ui/bits";

const ROLE_LABEL: Record<string, string> = { owner: "Festival director", core: "Core team", volunteer: "Volunteer", admin: "Admin" };
const slugify = (t: string) => t.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);

function CreateFest({ colleges, onCancel }: { colleges: College[]; onCancel: () => void }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [tagline, setTagline] = useState("");
  const [collegeId, setCollegeId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const fest = await api<Fest>("/api/fests/", { method: "POST", body: { name, slug, tagline: tagline || null, college_id: collegeId ? Number(collegeId) : null, status: "draft" } });
      router.push(`/committee/${fest.slug}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the fest.");
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="bg-white ring-1 ring-black/5 shadow-[var(--shadow-card)] mb-8 space-y-4 rounded-[2rem] p-6 sm:p-8">
      <h2 className="font-display text-xl font-extrabold tracking-tight">New fest</h2>
      <ErrorNote>{error}</ErrorNote>
      <Field label="Fest name">
        <input className="field" required value={name} placeholder="e.g. Mood Indigo 2026" onChange={(e) => { setName(e.target.value); if (!slugEdited) setSlug(slugify(e.target.value)); }} />
      </Field>
      <Field label="Web address" hint={`Your fest page will be at /fest/${slug || "your-fest"}`}>
        <input className="field" required value={slug} pattern="[a-z0-9]+(-[a-z0-9]+)*" title="Lowercase letters, numbers and single hyphens" onChange={(e) => { setSlugEdited(true); setSlug(e.target.value.toLowerCase()); }} />
      </Field>
      <Field label="Tagline"><input className="field" value={tagline} placeholder="One line about your fest" onChange={(e) => setTagline(e.target.value)} /></Field>
      <Field label="College">
        <select className="field" value={collegeId} onChange={(e) => setCollegeId(e.target.value)}>
          <option value="">Not listed</option>
          {colleges.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </Field>
      <p className="text-xs text-neutral-500">The fest starts as a draft that only your team can see. Make it live when you are ready.</p>
      <div className="flex gap-3">
        <Button type="submit" disabled={busy}>{busy ? "Creating…" : "Create fest"}</Button>
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}

export function CommitteeHome() {
  const { user } = useAuth();
  const [fests, setFests] = useState<MyFest[] | null>(null);
  const [colleges, setColleges] = useState<College[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const canCreate = user?.role === "organizer" || user?.role === "admin";

  useEffect(() => {
    api<MyFest[]>("/api/fests/mine").then(setFests).catch((e) => { setError(e instanceof Error ? e.message : "Could not load your fests."); setFests([]); });
    api<College[]>("/api/colleges/").then(setColleges).catch(() => {});
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-6 pb-8 pt-8">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-chip-ink">Committee</p>
          <h1 className="mt-1 font-display text-4xl font-bold tracking-tight sm:text-5xl">Your fests</h1>
          <p className="mt-3 max-w-xl text-neutral-500">Run events, registrations and your team in one place.</p>
        </div>
        {canCreate && !creating && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> New fest</Button>}
      </div>

      <ErrorNote>{error}</ErrorNote>
      {creating && <CreateFest colleges={colleges} onCancel={() => setCreating(false)} />}

      {fests === null ? (
        <div className="grid gap-5 md:grid-cols-2"><Skeleton className="h-32" /><Skeleton className="h-32" /></div>
      ) : fests.length === 0 ? (
        <EmptyState
          title={canCreate ? "No fests yet" : "You are not on a fest committee"}
          body={canCreate ? "Create your first fest to start publishing events." : "Committee tools are switched on by the HiveOut team. Once your account is set up you can create your fest here, or your fest director can add your email to the team."}
          action={canCreate ? <Button onClick={() => setCreating(true)}>Create a fest</Button> : undefined}
        />
      ) : (
        <div className="grid gap-5 md:grid-cols-2">
          {fests.map((f) => (
            <Link key={f.id} href={`/committee/${f.slug}`} className="bg-white ring-1 ring-black/5 shadow-[var(--shadow-card)] block rounded-3xl p-6 transition hover:-translate-y-1 hover:shadow-[var(--shadow-lift)]">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <Pill tone={f.status === "live" ? "green" : "neutral"}>{f.status === "live" ? "Live" : "Draft"}</Pill>
                <span className="text-xs font-medium text-neutral-500">{ROLE_LABEL[f.my_role] ?? f.my_role}</span>
              </div>
              <h2 className="font-display text-2xl font-extrabold tracking-tight">{f.name}</h2>
              {f.tagline && <p className="mt-1 line-clamp-1 text-neutral-500">{f.tagline}</p>}
              <p className="mt-4 text-sm text-neutral-500">{f.event_count} live event{f.event_count === 1 ? "" : "s"}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
