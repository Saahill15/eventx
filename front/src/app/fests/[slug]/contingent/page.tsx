import type { Metadata } from "next";
import { ContingentPortal } from "@/components/ContingentPortal";
import { RequireLogin } from "@/components/RequireLogin";

export const metadata: Metadata = { title: "Bring your college", robots: { index: false } };

export default async function ContingentPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return (
    <RequireLogin>
      <ContingentPortal slug={slug} />
    </RequireLogin>
  );
}
