import type { Metadata } from "next";
import { CommitteeHome } from "@/components/committee/CommitteeHome";
import { RequireLogin } from "@/components/RequireLogin";

export const metadata: Metadata = { title: "Committee dashboard", robots: { index: false } };

export default function CommitteePage() {
  return <RequireLogin><CommitteeHome /></RequireLogin>;
}
