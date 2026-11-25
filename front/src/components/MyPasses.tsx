"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { api } from "@/lib/api";
import type { Certificate, CityPass, FestEvent, FestPass, PaymentRow, Registration } from "@/lib/types";
import { formatDay, inr } from "@/lib/format";
import { Button } from "./ui/Button";
import { EmptyState, ErrorNote, Pill, Skeleton } from "./ui/bits";
import { Stagger, StaggerItem } from "./motion";
import { TicketShell } from "./TicketShell";
import { PayNow } from "./PayNow";

const tone = { approved: "green", pending: "amber", rejected: "red" } as const;
const word = { approved: "Confirmed", pending: "Waiting", rejected: "Not approved" } as const;

function RegistrationRow({ reg }: { reg: Registration }) {
  const [event, setEvent] = useState<FestEvent | null>(null);
  useEffect(() => { api<FestEvent>(`/api/events/${reg.event_id}`).then(setEvent).catch(() => {}); }, [reg.event_id]);
  return (
    <li className="flex items-center justify-between gap-3 py-3">
      <Link href={`/events/${reg.event_id}`} className="min-w-0"><p className="truncate font-semibold hover:underline">{event?.title ?? "Event"}</p>{event && <p className="text-xs text-mute">{formatDay(event.date)}</p>}</Link>
      {reg.awaiting_payment && reg.approval_status !== "rejected" ? <Pill tone="amber">Pay {inr(reg.amount_due ?? 0)}</Pill> : <Pill tone={tone[reg.approval_status]}>{word[reg.approval_status]}</Pill>}
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

function MyPayments({ items }: { items: PaymentRow[] }) {
  if (items.length === 0) return null;
  return (
    <section className="mt-12" aria-label="My payments">
      <h2 className="font-display text-3xl font-bold tracking-tight">My payments</h2>
      <ul className="mt-4 divide-y divide-black/5 rounded-3xl bg-wash px-5">{items.map((p) => (
        <li key={p.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
          <div className="min-w-0"><p className="truncate font-semibold">{p.event_title ?? p.description ?? "Payment"}</p><p className="text-sm text-mute">{p.paid_at ? formatDay(p.paid_at.slice(0, 10)) : ""}{p.method ? ` · ${p.method.toUpperCase()}` : ""}</p>
            {p.refunds.filter((r) => r.status !== "failed").map((r) => <p key={r.id} className="text-sm text-emerald-700">Refund of {inr(r.amount)} {r.status === "done" ? "sent" : "on its way"}</p>)}</div>
          <p className="font-semibold">{inr(p.amount)}</p>
        </li>
      ))}</ul>
    </section>
  );
}

function PayPending({ regs }: { regs: Registration[] }) {
  const due = regs.filter((r) => r.awaiting_payment && r.approval_status !== "rejected");
  if (due.length === 0) return null;
  return (
    <section className="mb-8 space-y-3" aria-label="Waiting for payment">
      {due.map((r) => <PayRow key={r.id} reg={r} />)}
    </section>
  );
}

function PayRow({ reg }: { reg: Registration }) {
  const [event, setEvent] = useState<FestEvent | null>(null);
  useEffect(() => { api<FestEvent>(`/api/events/${reg.event_id}`).then(setEvent).catch(() => {}); }, [reg.event_id]);
  return (
    <div className="grid items-center gap-3 rounded-3xl bg-tint p-5 sm:grid-cols-[1fr_auto]">
      <div><p className="font-semibold">Pay to confirm your seat: {event?.title ?? "an event"}</p><p className="text-sm text-tint-ink">Your seat is held for a short while. If the payment does not arrive, it goes back.</p></div>
      <div className="sm:w-64"><PayNow endpoint={`/api/payments/registrations/${reg.id}/checkout`} amount={reg.amount_due ?? 0} holdUntil={reg.hold_expires_at} compact /></div>
    </div>
  );
}

function MyCertificates({ items }: { items: Certificate[] }) {
  if (items.length === 0) return null;
  return (
    <section className="mt-12" aria-label="My certificates">
      <h2 className="font-display text-3xl font-bold tracking-tight">My certificates</h2>
      <ul className="mt-4 grid gap-3 md:grid-cols-2">{items.map((c) => (
        <li key={c.id} className={`flex items-center justify-between gap-4 rounded-3xl bg-wash p-5 ${c.revoked ? "opacity-60" : ""}`}>
          <div className="min-w-0"><p className="truncate font-semibold">{c.title}{c.award_text ? ` · ${c.award_text}` : ""}</p><p className="truncate text-sm text-mute">{c.event_title ? `${c.event_title} · ` : ""}{c.fest_name}</p></div>
          <div className="flex shrink-0 items-center gap-3">{c.revoked && <Pill tone="red">Withdrawn</Pill>}<Link href={`/certificates/${c.code}`} className="text-sm font-semibold underline underline-offset-4">View and print</Link></div>
        </li>
      ))}</ul>
    </section>
  );
}

export function MyPasses() {
  const [festPasses, setFestPasses] = useState<FestPass[] | null>(null);
  const [regs, setRegs] = useState<Registration[]>([]);
  const [cityPasses, setCityPasses] = useState<CityPass[]>([]);
  const [certs, setCerts] = useState<Certificate[]>([]);
  const [paid, setPaid] = useState<PaymentRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => { api<Certificate[]>("/api/users/me/certificates").then(setCerts).catch(() => {}); api<PaymentRow[]>("/api/payments/mine").then(setPaid).catch(() => {}); }, []);
  useEffect(() => {
    Promise.all([api<FestPass[]>("/api/users/me/fest-passes"), api<Registration[]>("/api/fest-events/my-registrations"), api<CityPass[]>("/api/passes/my")])
      .then(([fp, r, cp]) => { setFestPasses(fp); setRegs(r); setCityPasses(cp); })
      .catch((e) => { setError(e instanceof Error ? e.message : "Could not load your passes."); setFestPasses([]); });
  }, []);

  if (festPasses === null) return <div className="grid gap-6 md:grid-cols-2"><Skeleton className="h-80" /><Skeleton className="h-80" /></div>;
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (festPasses.length === 0 && cityPasses.length === 0 && certs.length === 0) return <EmptyState title="No passes yet" body="Get a free pass from any fest page and it will show up here with your QR code." action={<Button href="/fests">Browse college fests</Button>} />;
  return (
    <>
      <PayPending regs={regs} />
      <Stagger className="grid items-start gap-6 md:grid-cols-2">
        {festPasses.map((p) => <StaggerItem key={p.id}><FestPassCard pass={p} regs={regs.filter((r) => r.fest_pass_id === p.id)} /></StaggerItem>)}
        {cityPasses.map((p) => <StaggerItem key={p.id}><CityPassRow pass={p} /></StaggerItem>)}
      </Stagger>
      <MyCertificates items={certs} />
      <MyPayments items={paid} />
    </>
  );
}
