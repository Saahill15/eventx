import type { Metadata } from "next";
import { ProfileView } from "@/components/ProfileView";
import { RequireLogin } from "@/components/RequireLogin";

export const metadata: Metadata = { title: "Profile", robots: { index: false } };

export default function ProfilePage() {
  return (
    <RequireLogin>
      <div className="mx-auto max-w-2xl px-6 pb-8 pt-8">
        <h1 className="mb-8 font-display text-4xl font-black tracking-tight">Profile</h1>
        <ProfileView />
      </div>
    </RequireLogin>
  );
}
