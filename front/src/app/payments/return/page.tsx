import type { Metadata } from "next";
import { Suspense } from "react";
import { PaymentReturn } from "@/components/PaymentReturn";
import { RequireLogin } from "@/components/RequireLogin";

export const metadata: Metadata = { title: "Your payment", robots: { index: false } };

export default function PaymentReturnPage() {
  return (
    <RequireLogin adminTo="/admin">
      <div className="mx-auto max-w-xl px-5 pb-10 pt-14 sm:px-8">
        <Suspense fallback={null}><PaymentReturn /></Suspense>
      </div>
    </RequireLogin>
  );
}
