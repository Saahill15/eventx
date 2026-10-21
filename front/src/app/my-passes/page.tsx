import type { Metadata } from "next";
import { MyPasses } from "@/components/MyPasses";
import { RequireLogin } from "@/components/RequireLogin";

export const metadata: Metadata = { title: "My passes", robots: { index: false } };

export default function MyPassesPage() {
  return (
    <RequireLogin>
      <div className="mx-auto max-w-3xl px-6 pb-8 pt-8">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-hive-ink">Wallet</p>
        <h1 className="mt-1 font-display text-4xl font-black tracking-tight sm:text-5xl">My passes</h1>
        <p className="mb-8 mt-3 text-neutral-500">Show the QR code at the gate. Keep your screen bright.</p>
        <MyPasses />
      </div>
    </RequireLogin>
  );
}
