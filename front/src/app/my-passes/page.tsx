import type { Metadata } from "next";
import { MyPasses } from "@/components/MyPasses";
import { RequireLogin } from "@/components/RequireLogin";

export const metadata: Metadata = { title: "My passes", robots: { index: false } };

export default function MyPassesPage() {
  return (
    <RequireLogin>
      <div className="mx-auto max-w-7xl px-5 pb-4 pt-10 sm:px-8 sm:pt-14">
        <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-amber-ink">Wallet</p>
        <h1 className="font-display text-5xl font-bold tracking-[-0.03em] sm:text-6xl">My passes</h1>
        <p className="mb-10 mt-3 text-mute">Show the QR code at the gate. Turn your screen brightness up.</p>
        <MyPasses />
      </div>
    </RequireLogin>
  );
}
