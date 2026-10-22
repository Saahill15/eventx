"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { EmptyState, ErrorNote, Pill, Skeleton } from "@/components/ui/bits";
import { Chips, when } from "./shared";

interface AuthEvent { id: number; at: string; portal: "public" | "admin"; email: string | null; user_id: number | null; ip: string | null; success: boolean; reason: string }

const REASON: Record<string, string> = {
  ok: "Signed in", bad_credentials: "Wrong email or password", not_admin: "Not an admin account", locked: "Blocked: too many attempts",
  disabled: "Account suspended", admin_on_public_page: "Admin tried the public sign-in",
};

export function SecurityTab() {
  const [filter, setFilter] = useState<"all" | "failed">("failed");
  const [rows, setRows] = useState<AuthEvent[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    api<AuthEvent[]>(`/api/admin/security-log?limit=200${filter === "failed" ? "&failed_only=true" : ""}`).then((r) => { setRows(r); setError(""); }).catch((e) => { setError(e instanceof Error ? e.message : "Could not load."); setRows([]); });
  }, [filter]);
  useEffect(() => { setRows(null); load(); }, [load]);

  return (
    <div>
      <Chips value={filter} onChange={setFilter} options={[{ id: "failed", label: "Failed attempts" }, { id: "all", label: "Everything" }]} />
      <ErrorNote>{error}</ErrorNote>
      {rows === null ? <Skeleton className="h-40" /> : rows.length === 0 ? <EmptyState title="Nothing here" body={filter === "failed" ? "No failed sign-in attempts." : "No sign-in attempts yet."} /> : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead><tr className="border-b border-black/5 text-xs uppercase tracking-wider text-mute"><th className="px-5 py-3">When</th><th className="px-3 py-3">Where</th><th className="px-3 py-3">Email</th><th className="px-3 py-3">From</th><th className="px-5 py-3">Result</th></tr></thead>
            <tbody className="divide-y divide-black/5">
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="whitespace-nowrap px-5 py-3 text-mute">{when(r.at)}</td>
                  <td className="px-3 py-3">{r.portal === "admin" ? <Pill tone="amber">Admin page</Pill> : <Pill>Public page</Pill>}</td>
                  <td className="max-w-[16rem] truncate px-3 py-3 font-medium">{r.email || "—"}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-mute">{r.ip ?? "—"}</td>
                  <td className="px-5 py-3"><Pill tone={r.success ? "green" : "red"}>{REASON[r.reason] ?? r.reason}</Pill></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
