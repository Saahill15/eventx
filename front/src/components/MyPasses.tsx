"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { api } from "@/lib/api";
import type { CityPass, FestEvent, FestPass, Registration } from "@/lib/types";
import { formatDay } from "@/lib/format";
import { Button } from "./ui/Button";
import { EmptyState, ErrorNote, Pill, Skeleton } from "./ui/bits";
import { Stagger, StaggerItem } from "./motion";
import { TicketShell } from "./TicketShell";

const tone = { approved: "green", pending: "amber", rejected: "red" } as const;
const word = { approved: "Confirmed", pending: "Waiting", rejected: "Not approved" } as const;

function RegistrationRow({ reg }: { reg: Registration }) {
  const [event, setEvent] = useState<FestEvent | null>(null);
  useEffect(() => { api<FestEvent>(`/api/events/${reg.event_id}`).then(setEvent).catch(() => {}); }, [reg.event_id]);
  return (
    <li className="flex items-center justify-between gap-3 py-3">
      <Link href={`/events/${reg.event_id}`} className="min-w-0"><p className="truncate font-semibold hover:underline">{event?.title ?? "Event"}</p>{event && <p className="text-xs text-mute">{formatDay(event.date)}</p>}</Link>
      <Pill tone={tone[reg.approval_status]}>{word[reg.approval_status]}</Pill>
    </li>
  );
}

function FestPassCard({ pass, regs }: { pass: FestPass; regs: Registration[] }) {
  const blocked = pass.status !== "approved";
  return (
    <TicketShell
      head={<div className="flex items-start justify-between gap-3"><div><p className="text-[11px] font-bold uppercase tracking-[0.18em] text-chip-ink">Fest pass</p><Link href={`/fests/${pass.fest_slug}`} className="font-display text-2xl font-bold leading-tight tracking-tight hover:underline">{pass.fest_name ?? "Fest"}</Link></div><Pill tone={blocked ? "red" : pass.checked_in ? "neutral" : "green"}>{blocked ? "Blocked" : pass.checked_in ? "Used" : "Valid"}</Pill></div>}
    >
      <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
        <motion.div whileHover={{ scale: 1.04 }} className="shrink-0 rounded-2xl bg-white p-3 ring-1 ring-black/10"><QRCodeSVG value={pass.qr_code} size={156} aria-label="Pass QR code" /></motion.div>
        <div className="w-full min-w-0">
          <p className="mb-1 text-sm font-bold">Your registrations</p>
          {regs.length === 0 ? <p className="text-sm text-mute">None yet. Open the fest to register for events.</p> : <ul className="divide-y divide-black/5">{regs.map((r) => <RegistrationRow key={r.id} reg={r} />)}</ul>}
        </div>
      </div>
    </TicketShell>
  );
}

function CityPassRow({ pass }: { pass: CityPass }) {
  const [event, setEvent] = useState<FestEvent | null>(null);
  useEffect(() => { api<FestEvent>(`/api/events/${pass.event_id}`).then(setEvent).catch(() => {}); }, [pass.event_id]);
  return (
    <div className="flex items-center justify-between gap-4 rounded-3xl bg-wash p-5">
      <div className="min-w-0"><Link href={`/events/${pass.event_id}`} className="truncate font-display text-lg font-bold tracking-tight hover:underline">{event?.title ?? "Event"}</Link><p className="text-sm text-mute">Code <span className="font-mono font-semibold text-ink">{pass.pass_code}</span></p></div>
      <Pill tone={pass.payment_status === "free" ? "green" : "amber"}>{pass.payment_status === "free" ? "Free" : pass.payment_status}</Pill>
    </div>
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

  if (festPasses === null) return <div className="grid gap-6 md:grid-cols-2"><Skeleton className="h-80" /><Skeleton className="h-80" /></div>;
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (festPasses.length === 0 && cityPasses.length === 0) return <EmptyState title="No passes yet" body="Get a free pass from any fest page and it will show up here with your QR code." action={<Button href="/fests">Browse college fests</Button>} />;
  return (
    <Stagger className="grid items-start gap-6 md:grid-cols-2">
      {festPasses.map((p) => <StaggerItem key={p.id}><FestPassCard pass={p} regs={regs.filter((r) => r.fest_pass_id === p.id)} /></StaggerItem>)}
      {cityPasses.map((p) => <StaggerItem key={p.id}><CityPassRow pass={p} /></StaggerItem>)}
    </Stagger>
  );
}
