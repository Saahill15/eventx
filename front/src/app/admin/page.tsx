import type { Metadata } from "next";
import { AdminDashboard } from "@/components/admin/AdminDashboard";
import { RequireLogin } from "@/components/RequireLogin";

export const metadata: Metadata = { title: "Admin", robots: { index: false } };

export default function AdminPage() {
  return <RequireLogin><AdminDashboard /></RequireLogin>;
}
