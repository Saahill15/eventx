"use client";

import { Bell, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AccountNotice } from "@/lib/types";
import { formatDay } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Pill, Skeleton } from "@/components/ui/bits";

const STATUS: Record<string, { label: string; tone: "neutral" | "green" | "red" | "amber" }> = {
  accepted: { label: "Accepted", tone: "green" },
  declined: { label: "Declined", tone: "red" },
  cancelled: { label: "Withdrawn", tone: "neutral" },
};

/** Bell next to the profile button. Clicking it opens a dialog with the account's notices. There is no separate page. */
export function NotificationBell() {
  const { user } = useAuth();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);

  const refreshCount = useCallback(() => {
    api<{ count: number }>("/api/users/me/account-notices/unread-count").then((r) => setUnread(r.count)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!user) return;
    refreshCount();
    const timer = setInterval(refreshCount, 60_000);
    return () => clearInterval(timer);
  }, [user, refreshCount]);

  if (!user) return null;
  const label = unread > 0 ? `Notifications, ${unread} unread` : "Notifications";
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={label}
        aria-haspopup="dialog"
        className="relative flex h-11 w-11 items-center justify-center rounded-2xl bg-white shadow-[var(--shadow-card)] transition hover:bg-wash active:scale-95"
      >
        <Bell className="h-[18px] w-[18px]" />
        {unread > 0 && <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-brand px-1 text-[11px] font-bold text-white">{unread > 9 ? "9+" : unread}</span>}
      </button>
      {open && <NotificationDialog onClose={() => { setOpen(false); refreshCount(); }} />}
    </>
  );
}

function NotificationDialog({ onClose }: { onClose: () => void }) {
  const [notes, setNotes] = useState<AccountNotice[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [needsVerify, setNeedsVerify] = useState(false);

  const load = useCallback(() => {
    api<AccountNotice[]>("/api/users/me/account-notices")
      .then((rows) => { setNotes(rows); setError(""); })
      .catch((e) => { setError(e instanceof Error ? e.message : "Could not load your notifications."); setNotes([]); });
  }, []);

  useEffect(() => {
    load();
    // Opening the dialog counts as having seen the notices. Invitations stay actionable until answered.
    api("/api/users/me/account-notices/read-all", { method: "POST" }).catch(() => {});
  }, [load]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const answer = async (n: AccountNotice, accept: boolean) => {
    if (!n.invite_id) return;
    setBusy(true); setError(""); setNeedsVerify(false);
    try {
      await api(`/api/fest-invites/${n.invite_id}/${accept ? "accept" : "decline"}`, { method: "POST" });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That did not work.");
      // Accepting needs a verified student. The invitation stays open, so they can verify and come back
      setNeedsVerify(e instanceof ApiError && e.status === 403);
    }
    setBusy(false);
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-end bg-ink/20 p-4 pt-20 sm:pt-24" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Notifications" onClick={(e) => e.stopPropagation()} className="card flex max-h-[75vh] w-full max-w-md flex-col overflow-hidden p-0 shadow-[var(--shadow-pop)]">
        <div className="flex items-center justify-between border-b border-black/5 px-5 py-4">
          <p className="font-display text-lg font-extrabold tracking-tight">Notifications</p>
          <button type="button" onClick={onClose} aria-label="Close notifications" className="flex h-9 w-9 items-center justify-center rounded-xl text-mute transition hover:bg-wash"><X className="h-4 w-4" /></button>
        </div>
        <div className="overflow-y-auto p-4">
          <ErrorNote>{error}</ErrorNote>
          {needsVerify && <p className="mb-3 text-sm"><Link href="/profile#student" onClick={onClose} className="font-semibold text-tint-ink underline">Verify your student status</Link> to join, then accept again.</p>}
          {notes === null ? <Skeleton className="h-24" /> : notes.length === 0 ? <EmptyState title="Nothing new" body="Team invitations and updates about your account appear here." /> : (
            <ul className="space-y-3">
              {notes.map((n) => (
                <li key={n.id} className={`rounded-2xl p-4 ${n.read_at ? "bg-wash" : "bg-tint"}`}>
                  <div className="flex items-start justify-between gap-3">
                    <p className="font-semibold">{n.title}</p>
                    <time className="shrink-0 text-xs text-mute">{formatDay(n.created_at)}</time>
                  </div>
                  <p className="mt-1 text-sm text-mute">{n.body}</p>
                  {n.kind === "fest_invite" && n.invite_status === "pending" && (
                    <div className="mt-3 flex gap-2">
                      <Button size="sm" disabled={busy} onClick={() => answer(n, true)}>Accept</Button>
                      <Button size="sm" variant="outline" disabled={busy} onClick={() => answer(n, false)}>Decline</Button>
                    </div>
                  )}
                  {n.invite_status && STATUS[n.invite_status] && <div className="mt-3"><Pill tone={STATUS[n.invite_status].tone}>{STATUS[n.invite_status].label}</Pill></div>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
