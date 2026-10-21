"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "./ui/Button";
import { ErrorNote, Pill } from "./ui/bits";

export function ProfileView() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (!user) return null;

  const requestOrganizer = async () => {
    setBusy(true); setError(""); setMessage("");
    try {
      const res = await api<{ message: string; status?: string }>("/api/users/request-organizer", { method: "POST" });
      setMessage(res.status ? `${res.message}. Status: ${res.status}.` : res.message);
    } catch (e) { setError(e instanceof Error ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-5">
      <div className="glass-strong flex items-center gap-5 rounded-[2rem] p-7">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-hive font-display text-2xl font-black text-ink">{user.name.charAt(0).toUpperCase()}</div>
        <div className="min-w-0">
          <p className="truncate font-display text-2xl font-black tracking-tight">{user.name}</p>
          <p className="truncate text-neutral-500">{user.email}</p>
          <div className="mt-2"><Pill tone="amber">{user.role === "user" ? "Student" : user.role}</Pill></div>
        </div>
      </div>

      {user.role === "user" && (
        <div className="glass rounded-3xl p-7">
          <p className="font-display text-lg font-extrabold tracking-tight">Run a fest?</p>
          <p className="mb-4 mt-1 text-neutral-500">Request organiser access to publish events and manage registrations for your committee.</p>
          <ErrorNote>{error}</ErrorNote>
          {message && <p className="mb-3 text-sm font-medium text-emerald-700">{message}</p>}
          <Button onClick={requestOrganizer} disabled={busy} variant="dark">{busy ? "Sending…" : "Request organiser access"}</Button>
        </div>
      )}

      <Button variant="glass" onClick={() => { logout(); router.push("/"); }}>Sign out</Button>
    </div>
  );
}
