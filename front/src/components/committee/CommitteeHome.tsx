"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canHostFests } from "@/lib/permissions";
import type { College, Fest, MyFest } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Pill, Skeleton } from "@/components/ui/bits";
import { Field } from "@/components/ui/bits";
import { ReviewPill } from "./CommitteeShell";

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
      const fest = await api<Fest>("/api/fests/", { method: "POST", body: { name, slug, tagline: tagline || null, college_id: Number(collegeId) } });
      router.push(`/dashboard/fests/${fest.slug}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the fest.");
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="card mb-8 max-w-xl space-y-4 p-6 sm:p-8">
      <h2 className="font-display text-xl font-extrabold tracking-tight">New fest</h2>
      <ErrorNote>{error}</ErrorNote>
      <Field label="Fest name">
        <input className="field" required value={name} placeholder="e.g. Mood Indigo 2026" onChange={(e) => { setName(e.target.value); if (!slugEdited) setSlug(slugify(e.target.value)); }} />
      </Field>
      <Field label="Web address" hint={`Your fest page will be at /fests/${slug || "your-fest"}. This cannot be changed later. You can claim a shorter custom link afterwards.`}>
        <input className="field" required value={slug} pattern="[a-z0-9]+(-[a-z0-9]+)*" title="Lowercase letters, numbers and single hyphens" onChange={(e) => { setSlugEdited(true); setSlug(e.target.value.toLowerCase()); }} />
      </Field>
      <Field label="Tagline"><input className="field" value={tagline} placeholder="One line about your fest" onChange={(e) => setTagline(e.target.value)} /></Field>
      <Field label="College" hint={colleges.length ? undefined : "No college is assigned to your account yet. Ask HiveOut to add yours."}>
        <select className="field" required value={collegeId} onChange={(e) => setCollegeId(e.target.value)}>
          <option value="">Choose your college</option>
          {colleges.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </Field>
      <p className="text-xs text-neutral-500">The fest starts as a draft that only your team can see. Fill in its details, add events, then send it to HiveOut for review.</p>
      <div className="flex gap-3">
        <Button type="submit" disabled={busy || colleges.length === 0}>{busy ? "Creating…" : "Create fest"}</Button>
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
  const canCreate = canHostFests(user);

  useEffect(() => { if (window.location.hash === "#new") setCreating(true); }, []);
  useEffect(() => {
    api<MyFest[]>("/api/fests/mine").then(setFests).catch((e) => { setError(e instanceof Error ? e.message : "Could not load your fests."); setFests([]); });
    api<College[]>("/api/colleges/").then((all) => setColleges(user?.role === "organizer" ? all.filter((c) => user.college_ids.includes(c.id) && c.partner_status === "partner") : all)).catch(() => {});
  }, [user]);

  return (
    <div>
      {canCreate && !creating && <div className="mb-6"><Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> New fest</Button></div>}

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
        <div className="grid gap-5 [grid-template-columns:repeat(auto-fill,minmax(22rem,1fr))]">
          {fests.map((f) => (
            <Link key={f.id} href={`/dashboard/fests/${f.slug}`} className="card block p-6 transition hover:-translate-y-1 hover:shadow-[var(--shadow-lift)]">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <Pill tone={f.status === "live" ? "green" : "neutral"}>{f.status === "live" ? "Live" : "Not live"}</Pill>
                <ReviewPill status={f.review_status} />
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
