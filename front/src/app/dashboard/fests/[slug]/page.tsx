import type { Metadata } from "next";
import { FestManager } from "@/components/committee/FestManager";

export const metadata: Metadata = { title: "Manage fest", robots: { index: false } };

export default async function ManageFestPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <FestManager slug={slug} />;
}
