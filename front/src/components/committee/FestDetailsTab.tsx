"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { FestManage } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Field, Notice } from "@/components/ui/bits";
import { ImageUpload } from "@/components/ui/ImageUpload";
import { SectionsEditor } from "./SectionsEditor";

const blank = (v: string) => (v.trim() ? v.trim() : null);

function Card({ title, children, note }: { title: string; children: React.ReactNode; note?: string }) {
  return <section className="card space-y-4 p-6 sm:p-7"><div><h3 className="font-display text-lg font-semibold tracking-tight">{title}</h3>{note && <p className="mt-1 text-sm text-mute">{note}</p>}</div>{children}</section>;
}

export function FestDetailsTab({ fest, frozen, onSaved }: { fest: FestManage; frozen: boolean; onSaved: () => void }) {
  const [f, setF] = useState({
    name: fest.name, tagline: fest.tagline ?? "", description: fest.description ?? "", start_date: fest.start_date ?? "", end_date: fest.end_date ?? "",
    campus_address: fest.campus_address ?? "", map_url: fest.map_url ?? "", instagram_url: fest.instagram_url ?? "", website_url: fest.website_url ?? "",
    contact_name: fest.contact_name ?? "", contact_email: fest.contact_email ?? "", contact_phone: fest.contact_phone ?? "",
    faculty_name: fest.faculty_name ?? "", faculty_phone: fest.faculty_phone ?? "", faculty_email: fest.faculty_email ?? "",
  });
  const [banner, setBanner] = useState<string | null>(fest.banner_url);
  const [logo, setLogo] = useState<string | null>(fest.logo_url);
  const [sections, setSections] = useState(fest.extra_sections ?? []);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => { setSaved(false); setF((x) => ({ ...x, [k]: e.target.value })); };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api(`/api/fests/${fest.slug}`, { method: "PATCH", body: {
        name: f.name.trim(), tagline: blank(f.tagline), description: blank(f.description), start_date: blank(f.start_date), end_date: blank(f.end_date),
        campus_address: blank(f.campus_address), map_url: blank(f.map_url), instagram_url: blank(f.instagram_url), website_url: blank(f.website_url),
        contact_name: blank(f.contact_name), contact_email: blank(f.contact_email), contact_phone: blank(f.contact_phone),
        faculty_name: blank(f.faculty_name), faculty_phone: blank(f.faculty_phone), faculty_email: blank(f.faculty_email),
        banner_url: banner, logo_url: logo, extra_sections: sections.filter((s) => s.title.trim() && s.body.trim()),
      } });
      setSaved(true); onSaved();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save."); }
    setBusy(false);
  };

  return (
    <form onSubmit={save} className="max-w-4xl space-y-5">
      {frozen && <Notice tone="warn">This fest is with HiveOut for review, so it cannot be edited. Withdraw it from the Overview tab to make changes.</Notice>}
      <ErrorNote>{error}</ErrorNote>
      <fieldset disabled={frozen} className="space-y-5">
        <Card title="The basics" note="Changing the name of an approved fest sends it back to review and takes it offline.">
          <Field label="Fest name"><input className="field" required value={f.name} onChange={set("name")} /></Field>
          <Field label="Tagline"><input className="field" value={f.tagline} onChange={set("tagline")} maxLength={500} placeholder="One line about your fest" /></Field>
          <Field label="About the fest"><textarea className="field min-h-32" value={f.description} onChange={set("description")} maxLength={5000} /></Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Starts"><input className="field" type="date" value={f.start_date} onChange={set("start_date")} /></Field>
            <Field label="Ends"><input className="field" type="date" value={f.end_date} onChange={set("end_date")} /></Field>
          </div>
        </Card>

        <Card title="Pictures">
          <div className="grid gap-6 sm:grid-cols-2">
            <ImageUpload label="Banner" value={banner} onChange={(u) => { setSaved(false); setBanner(u); }} aspect="aspect-[21/9]" />
            <ImageUpload label="Logo (optional)" value={logo} onChange={(u) => { setSaved(false); setLogo(u); }} aspect="aspect-square max-w-[11rem]" />
          </div>
        </Card>

        <Card title="Where it happens">
          <Field label="Campus address"><input className="field" value={f.campus_address} onChange={set("campus_address")} maxLength={500} /></Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Map link" hint="A Google Maps link"><input className="field" type="url" value={f.map_url} onChange={set("map_url")} placeholder="https://maps.app.goo.gl/…" /></Field>
            <Field label="Instagram"><input className="field" type="url" value={f.instagram_url} onChange={set("instagram_url")} placeholder="https://instagram.com/…" /></Field>
            <Field label="Website"><input className="field" type="url" value={f.website_url} onChange={set("website_url")} placeholder="https://…" /></Field>
          </div>
        </Card>

        <Card title="Contacts for HiveOut" note="Private. Only the HiveOut team sees these when reviewing your fest.">
          <p className="text-sm font-semibold">Committee contact</p>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Name"><input className="field" value={f.contact_name} onChange={set("contact_name")} /></Field>
            <Field label="Email"><input className="field" type="email" value={f.contact_email} onChange={set("contact_email")} /></Field>
            <Field label="Phone"><input className="field" type="tel" value={f.contact_phone} onChange={set("contact_phone")} placeholder="+91 98765 43210" /></Field>
          </div>
          <p className="text-sm font-semibold">Faculty coordinator <span className="font-normal text-mute">(optional)</span></p>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Name"><input className="field" value={f.faculty_name} onChange={set("faculty_name")} /></Field>
            <Field label="Email"><input className="field" type="email" value={f.faculty_email} onChange={set("faculty_email")} /></Field>
            <Field label="Phone"><input className="field" type="tel" value={f.faculty_phone} onChange={set("faculty_phone")} /></Field>
          </div>
        </Card>

        <Card title="More about the fest"><SectionsEditor value={sections} onChange={(v) => { setSaved(false); setSections(v); }} /></Card>
      </fieldset>

      {!frozen && <div className="flex items-center gap-3"><Button type="submit" size="lg" disabled={busy}>{busy ? "Saving…" : "Save details"}</Button>{saved && <span className="text-sm font-medium text-emerald-700">Saved</span>}</div>}
    </form>
  );
}
