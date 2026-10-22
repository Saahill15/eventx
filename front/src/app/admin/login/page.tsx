import type { Metadata } from "next";
import { AdminSignIn } from "@/components/admin/AdminSignIn";

export const metadata: Metadata = { title: "Admin sign in", robots: { index: false } };

export default async function AdminLoginPage({ searchParams }: { searchParams: Promise<{ next?: string; expired?: string }> }) {
  const { next, expired } = await searchParams;
  return <AdminSignIn next={next} expired={expired === "1"} />;
}
