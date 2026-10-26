"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { NotificationBell } from "./NotificationBell";
import { ProfileMenu } from "./ProfileMenu";

/** Right side of the organiser dashboard's top bar: "View site ↗" and the same profile pill the admin has. */
export function OrganiserProfileMenu({ role }: { role: string }) {
  const { user } = useAuth();
  return (
    <div className="ml-auto flex items-center gap-4">
      <Link href="/" className="flex items-center gap-1 text-[14px] font-medium text-[#4A5E5F] transition-colors hover:text-[#0B2625]">View site <ArrowUpRight className="h-3.5 w-3.5" /></Link>
      {user && <NotificationBell />}
      {user && <ProfileMenu name={user.name} email={user.email ?? ""} role={role} links={[{ href: "/", label: "View the site" }, { href: "/my-passes", label: "My passes" }, { href: "/profile", label: "Profile and security" }]} />}
    </div>
  );
}
