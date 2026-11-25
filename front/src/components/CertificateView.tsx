"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Certificate, CertificateCheck } from "@/lib/types";
import { formatDay } from "@/lib/format";
import { Button } from "./ui/Button";
import { Skeleton } from "./ui/bits";

/** The certificate itself, laid out to print on one landscape page. */
export function CertificateSheet({ c }: { c: Certificate }) {
  return (
    <article className={`relative mx-auto aspect-[1.414/1] w-full max-w-4xl border-[10px] border-double border-ink/80 bg-white p-8 text-center text-ink shadow-sm print:max-w-none print:shadow-none sm:p-14 ${c.revoked ? "opacity-70" : ""}`} aria-label="Certificate">
      {c.revoked && <p className="absolute inset-x-0 top-1/2 -translate-y-1/2 -rotate-12 font-display text-6xl font-bold uppercase tracking-widest text-red-600/40 sm:text-8xl">Withdrawn</p>}
      <div className="flex h-full flex-col items-center justify-between">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.3em] text-mute sm:text-sm">{c.fest_name}</p>
          <h1 className="mt-3 font-display text-3xl font-bold tracking-tight sm:text-5xl">{c.title}</h1>
        </div>
        <div className="max-w-2xl">
          <p className="text-sm text-mute">This is proudly given to</p>
          <p className="my-2 border-b border-ink/30 pb-2 font-display text-3xl font-bold sm:text-5xl">{c.recipient_name}</p>
          {c.college_name && <p className="text-sm text-mute sm:text-base">{c.college_name}</p>}
          {c.award_text && <p className="mt-3 inline-block rounded-full bg-chip px-4 py-1 text-sm font-bold text-chip-ink">{c.award_text}</p>}
          <p className="mt-4 whitespace-pre-line text-sm leading-relaxed sm:text-lg">{c.body}</p>
        </div>
        <div className="w-full">
          {c.signatories.length > 0 && (
            <div className="mb-4 flex flex-wrap justify-center gap-10">{c.signatories.map((s, i) => <div key={i} className="min-w-32 border-t border-ink/40 pt-1 text-xs sm:text-sm"><p className="font-semibold">{s.name}</p><p className="text-mute">{s.title}</p></div>)}</div>
          )}
          <p className="text-[10px] text-mute sm:text-xs">Issued {formatDay(c.issued_at.slice(0, 10))} · Check it at <span className="font-mono">{typeof window === "undefined" ? "" : window.location.origin}/certificates/{c.code}</span></p>
        </div>
      </div>
    </article>
  );
}

/** The public check page: anyone with the code (or QR link) can see whether it is real. */
export function CertificateCheckPage({ code }: { code: string }) {
  const [result, setResult] = useState<CertificateCheck | null | "missing">(null);
  useEffect(() => { api<CertificateCheck>(`/api/certificates/${encodeURIComponent(code)}`).then(setResult).catch(() => setResult("missing")); }, [code]);
  if (result === null) return <Skeleton className="mx-auto h-96 max-w-4xl" />;
  if (result === "missing" || !result.certificate) {
    return (
      <div className="mx-auto max-w-xl rounded-3xl bg-wash p-8 text-center">
        <p className="font-display text-2xl font-bold">We have no certificate with this code</p>
        <p className="mt-2 text-mute">Check the code for typing mistakes. It has ten letters and numbers. If it still fails, ask the fest that gave it to you.</p>
        <Button href="/" className="mt-5">Back to HiveOut</Button>
      </div>
    );
  }
  const c = result.certificate;
  return (
    <div className="space-y-6">
      <div className={`mx-auto max-w-4xl rounded-2xl p-4 text-sm print:hidden ${result.revoked ? "bg-red-50 text-red-800" : "bg-emerald-50 text-emerald-900"}`} role="status">
        {result.revoked ? <><strong>This certificate was withdrawn</strong>{c.revoked_reason ? `: ${c.revoked_reason}` : "."} It is no longer valid.</> : <><strong>This is a real certificate</strong> issued by {c.fest_name} on HiveOut.</>}
      </div>
      <CertificateSheet c={c} />
      <div className="mx-auto flex max-w-4xl justify-between gap-3 print:hidden"><Link href="/my-passes" className="text-sm font-semibold underline underline-offset-4">My passes</Link><Button onClick={() => window.print()} disabled={result.revoked}>Print or save as PDF</Button></div>
    </div>
  );
}
