import type { Metadata } from "next";
import { AdminShell } from "@/components/admin/AdminShell";
import { RequireLogin } from "@/components/RequireLogin";

export const metadata: Metadata = { title: "Admin", robots: { index: false } };

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <RequireLogin loginPath="/admin/login"><AdminShell>{children}</AdminShell></RequireLogin>;
}
