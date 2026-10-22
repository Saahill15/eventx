import type { Metadata } from "next";
import { CommitteeShell } from "@/components/committee/CommitteeShell";
import { RequireLogin } from "@/components/RequireLogin";

export const metadata: Metadata = { title: "Dashboard", robots: { index: false } };

export default function CommitteeLayout({ children }: { children: React.ReactNode }) {
  return <RequireLogin><CommitteeShell>{children}</CommitteeShell></RequireLogin>;
}
