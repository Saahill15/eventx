import type { Metadata } from "next";
import { CertificateCheckPage } from "@/components/CertificateView";

export const metadata: Metadata = { title: "Check a certificate", robots: { index: false } };

export default async function CertificatePage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  return (
    <div className="mx-auto max-w-[1760px] px-5 pb-10 pt-10 sm:px-8 sm:pt-14">
      <CertificateCheckPage code={code} />
    </div>
  );
}
