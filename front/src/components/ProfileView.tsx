"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Button } from "./ui/Button";
import { Pill } from "./ui/bits";

export function ProfileView() {
  const { user, logout } = useAuth();
  const router = useRouter();
  if (!user) return null;

  return (
    <div className="space-y-5">
      <div className="card flex items-center gap-5 p-7">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-ink font-display text-2xl font-bold text-white">{user.name.charAt(0).toUpperCase()}</div>
        <div className="min-w-0">
          <p className="truncate font-display text-2xl font-semibold tracking-tight">{user.name}</p>
          <p className="truncate text-mute">{user.email}</p>
          <div className="mt-2"><Pill tone="amber">{user.role === "organizer" ? "Organiser" : user.role === "admin" ? "Admin" : "Member"}</Pill></div>
        </div>
      </div>
      <Button variant="outline" onClick={() => { logout(); router.push("/"); }}>Sign out</Button>
    </div>
  );
}
