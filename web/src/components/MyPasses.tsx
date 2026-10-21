"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { api } from "@/lib/api";
import type { CityPass, FestEvent, FestPass, Registration } from "@/lib/types";
import { formatDay } from "@/lib/format";
import { Button } from "./ui/Button";
import { EmptyState, ErrorNote, Pill, Skeleton } from "./ui/bits";

const statusTone = { approved: "green", pending: "amber", rejected: "red" } as const;

function RegistrationRow({ reg }: { reg: Registration }) {
  const [event, setEvent] = useState<FestEvent | null>(null);
  useEffect(() => { api<FestEvent>(`/api/events/${reg.event_id}`).then(setEvent).catch(() => {}); }, [reg.event_id]);
  return (
    <li className="flex items-center justify-between gap-3 py-3">
      <Link href={`/events/${reg.event_id}`} className="min-w-0">
        <p className="truncate font-medium hover:underline">{event?.title ?? "Event"}</p>
        {event && <p className="text-xs text-neutral-500">{formatDay(event.date)}</p>}
      </Link>
      <Pill tone={statusTone[reg.approval_status]}>{reg.approval_status === "approved" ? "Confirmed" : reg.approval_status === "pending" ? "Waiting" : "Not approved"}</Pill>
    </li>
  );
}

function FestPassCard({ pass, regs }: { pass: FestPass; regs: Registration[] }) {
  const blocked = pass.status !== "approved";
  return (
    <article className="glass-strong overflow-hidden rounded-[2rem]">
      <div className="flex items-start justify-between gap-4 bg-gradient-to-br from-hive-100 to-hive-50 px-6 py-5">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-hive-ink">Fest pass</p>
          <Link href={`/fest/${pass.fest_slug}`} className="font-display text-2xl font-black tracking-tight hover:underline">{pass.fest_name ?? "Fest"}</Link>
        </div>
        <Pill tone={blocked ? "red" : pass.checked_in ? "neutral" : "green"}>{blocked ? "Blocked" : pass.checked_in ? "Used" : "Valid"}</Pill>
      </div>
      <div className="grid gap-6 p-6 sm:grid-cols-[auto_1fr]">
        <div className="mx-auto rounded-2xl bg-white p-3 shadow-sm">
          <QRCodeSVG value={pass.qr_code} size={152} aria-label="Pass QR code" />
        </div>
        <div className="min-w-0">
          <p className="mb-1 text-sm font-semibold">Your registrations</p>
          {regs.length === 0 ? (
            <p className="text-sm text-neutral-500">None yet. Open the fest to register for events.</p>
          ) : (
            <ul className="divide-y divide-black/5">{regs.map((r) => <RegistrationRow key={r.id} reg={r} />)}</ul>
          )}
        </div>
      </div>
    </article>
  );
}

function CityPassRow({ pass }: { pass: CityPass }) {
  const [event, setEvent] = useState<FestEvent | null>(null);
  useEffect(() => { api<FestEvent>(`/api/events/${pass.event_id}`).then(setEvent).catch(() => {}); }, [pass.event_id]);
  return (
    <article className="glass flex items-center justify-between gap-4 rounded-3xl p-5">
      <div className="min-w-0">
        <Link href={`/events/${pass.event_id}`} className="truncate font-display text-lg font-extrabold tracking-tight hover:underline">{event?.title ?? "Event"}</Link>
        <p className="text-sm text-neutral-500">Code <span className="font-mono font-semibold text-ink">{pass.pass_code}</span></p>
      </div>
      <Pill tone={pass.payment_status === "free" ? "green" : "amber"}>{pass.payment_status === "free" ? "Free" : pass.payment_status}</Pill>
    </article>
  );
}

export function MyPasses() {
  const [festPasses, setFestPasses] = useState<FestPass[] | null>(null);
  const [regs, setRegs] = useState<Registration[]>([]);
  const [cityPasses, setCityPasses] = useState<CityPass[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api<FestPass[]>("/api/users/me/fest-passes"), api<Registration[]>("/api/fest-events/my-registrations"), api<CityPass[]>("/api/passes/my")])
      .then(([fp, r, cp]) => { setFestPasses(fp); setRegs(r); setCityPasses(cp); })
      .catch((e) => { setError(e instanceof Error ? e.message : "Could not load your passes."); setFestPasses([]); });
  }, []);

  if (festPasses === null) return <div className="space-y-5"><Skeleton className="h-64" /><Skeleton className="h-64" /></div>;
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (festPasses.length === 0 && cityPasses.length === 0) {
    return <EmptyState title="No passes yet" body="Get a free pass from any fest page and it will show up here with your QR code." action={<Button href="/fests">Browse college fests</Button>} />;
  }
  return (
    <div className="space-y-5">
      {festPasses.map((p) => <FestPassCard key={p.id} pass={p} regs={regs.filter((r) => r.fest_pass_id === p.id)} />)}
      {cityPasses.map((p) => <CityPassRow key={p.id} pass={p} />)}
    </div>
  );
}
