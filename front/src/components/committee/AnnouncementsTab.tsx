"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Announcement, FestEvent } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Field, Notice } from "@/components/ui/bits";

const when = (iso: string) => new Date(iso.endsWith("Z") ? iso : iso + "Z").toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

/** Notices to everyone holding a pass, or to the people registered for one event. Optionally also sent by email. */
export function AnnouncementsTab({ slug, live, events }: { slug: string; live: boolean; events: FestEvent[] }) {
  const [list, setList] = useState<Announcement[] | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [eventId, setEventId] = useState("");
  const [email, setEmail] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState("");

  const load = useCallback(() => { api<Announcement[]>(`/api/fests/${slug}/announcements`).then(setList).catch(() => setList([])); }, [slug]);
  useEffect(load, [load]);

  const post = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(""); setSent("");
    try {
      await api(`/api/fests/${slug}/announcements`, { method: "POST", body: { title: title.trim(), body: body.trim(), event_id: eventId ? Number(eventId) : null, send_email: email } });
      setTitle(""); setBody(""); setEmail(false); setSent("Posted. People see it in their notifications."); load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not post."); }
    setBusy(false);
  };
  const remove = async (id: number) => { if (window.confirm("Remove this announcement?")) { await api(`/api/fests/${slug}/announcements/${id}`, { method: "DELETE" }).catch(() => {}); load(); } };

  return (
    <div className="max-w-3xl space-y-6">
      {!live && <Notice tone="warn">Announcements open once your fest is live.</Notice>}
      <form onSubmit={post} className="card space-y-4 p-6">
        <h3 className="font-display text-lg font-semibold">New announcement</h3>
        <ErrorNote>{error}</ErrorNote>
        {sent && <Notice tone="ok">{sent}</Notice>}
        <Field label="To"><select className="field" value={eventId} onChange={(e) => setEventId(e.target.value)} disabled={!live}><option value="">Everyone with a pass for the fest</option>{events.filter((e) => !e.cancelled).map((e) => <option key={e.id} value={e.id}>Registered for: {e.title}</option>)}</select></Field>
        <Field label="Title"><input className="field" required maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} disabled={!live} placeholder="e.g. Venue changed" /></Field>
        <Field label="Message"><textarea className="field min-h-28" required maxLength={2000} value={body} onChange={(e) => setBody(e.target.value)} disabled={!live} /></Field>
        <label className="flex items-center gap-3 text-sm font-medium"><input type="checkbox" className="h-4 w-4 accent-[#111]" checked={email} onChange={(e) => setEmail(e.target.checked)} disabled={!live} /> Also send by email</label>
        <Button type="submit" disabled={busy || !live}>{busy ? "Posting…" : "Post announcement"}</Button>
      </form>

      {list && list.length === 0 ? <EmptyState title="Nothing posted yet" body="Announcements you post appear here." /> : (
        <div className="space-y-3">
          {list?.map((a) => (
            <div key={a.id} className="card p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0"><p className="font-semibold">{a.title}</p><p className="text-xs text-mute">{when(a.created_at)} · {a.event_title ? `Registered for ${a.event_title}` : "Whole fest"}{a.email_requested ? ` · emailed ${a.emails_sent}${a.emails_failed ? `, ${a.emails_failed} failed` : ""}` : ""}</p></div>
                <button onClick={() => remove(a.id)} className="shrink-0 text-sm font-semibold text-red-600 hover:underline">Remove</button>
              </div>
              <p className="mt-2 whitespace-pre-line text-sm text-neutral-700">{a.body}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
