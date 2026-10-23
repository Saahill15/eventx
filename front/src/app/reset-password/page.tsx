import type { Metadata } from "next";
import { ResetPassword } from "@/components/PasswordReset";

export const metadata: Metadata = { title: "Choose a new password", robots: { index: false } };

export default async function ResetPasswordPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams;
  return <ResetPassword token={token ?? ""} />;
}
