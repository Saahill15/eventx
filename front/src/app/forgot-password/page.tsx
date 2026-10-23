import type { Metadata } from "next";
import { ForgotPassword } from "@/components/PasswordReset";

export const metadata: Metadata = { title: "Forgot password", robots: { index: false } };

export default async function ForgotPasswordPage({ searchParams }: { searchParams: Promise<{ admin?: string }> }) {
  const { admin } = await searchParams;
  return <ForgotPassword admin={admin === "1"} />;
}
