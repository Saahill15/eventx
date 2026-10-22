"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Skeleton } from "./ui/bits";

/** Wrap pages that need an account. Sends signed-out visitors to sign in, then back here. */
export function RequireLogin({ children, adminTo, loginPath = "/login" }: { children: React.ReactNode; adminTo?: string; loginPath?: string }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace(`${loginPath}?next=${encodeURIComponent(pathname)}`);
    if (!loading && user?.role === "admin" && adminTo) router.replace(adminTo); // admins have their own dashboard
  }, [loading, user, router, pathname, adminTo, loginPath]);

  if (loading || !user || (adminTo && user.role === "admin")) {
    return <div className="mx-auto max-w-3xl space-y-4 px-6 py-10"><Skeleton className="h-10 w-48" /><Skeleton className="h-40" /><Skeleton className="h-40" /></div>;
  }
  return <>{children}</>;
}
