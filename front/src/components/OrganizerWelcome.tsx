"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PartyPopper } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { College } from "@/lib/types";
import { Button } from "./ui/Button";

/**
 * Shown once, right after an admin makes the account an organiser: on the next page load or sign-in.
 * Leaving it any way marks it as seen, so it never comes back.
 */
export function OrganizerWelcome() {
  const { user, refresh } = useAuth();
  const router = useRouter();
  const [colleges, setColleges] = useState<College[]>([]);
  const show = !!user && user.role === "organizer" && user.organizer_welcome_pending && user.profile_complete;

  useEffect(() => { if (show) api<College[]>("/api/colleges/").then(setColleges).catch(() => {}); }, [show]);
  if (!show || !user) return null;

  const names = user.college_ids.map((id) => colleges.find((c) => c.id === id)?.name).filter(Boolean) as string[];
  const done = async (go: boolean) => {
    await api("/api/users/me/organizer-welcome/seen", { method: "POST" }).catch(() => {});
    await refresh();
    if (go) router.push("/dashboard");
  };

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="welcome-title" className="fixed inset-0 z-[110] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
      <div className="card w-full max-w-lg p-8 text-center shadow-[var(--shadow-pop)] sm:p-10">
        <span className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-3xl bg-tint text-tint-ink"><PartyPopper className="h-8 w-8" /></span>
        <h2 id="welcome-title" className="font-display text-3xl font-bold tracking-tight">You are now an organiser</h2>
        <p className="mt-3 text-mute">Hi {user.first_name ?? user.name}, the HiveOut team has upgraded your account. You can now create and run fests{names.length ? <> for <strong className="text-ink">{names.join(", ")}</strong></> : null}.</p>
        <ul className="mx-auto mt-6 max-w-sm space-y-2 text-left text-sm text-neutral-700">
          <li className="flex gap-3"><span className="font-bold text-tint-ink">1</span> Create your fest and fill in its details and events.</li>
          <li className="flex gap-3"><span className="font-bold text-tint-ink">2</span> Send it to HiveOut for a quick review.</li>
          <li className="flex gap-3"><span className="font-bold text-tint-ink">3</span> Once approved, go live and let students register.</li>
        </ul>
        <div className="mt-8 flex flex-col gap-2 sm:flex-row sm:justify-center">
          <Button size="lg" onClick={() => done(true)}>See organiser tools</Button>
          <Button size="lg" variant="ghost" onClick={() => done(false)}>Maybe later</Button>
        </div>
      </div>
    </div>
  );
}
