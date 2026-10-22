"use client";

import { Plus, Trash2 } from "lucide-react";
import type { ExtraSection } from "@/lib/types";
import { Button } from "@/components/ui/Button";

const MAX = 10;

/** Extra blocks of information on a page, such as Rules, Prizes or Schedule. */
export function SectionsEditor({ value, onChange, hint }: { value: ExtraSection[]; onChange: (v: ExtraSection[]) => void; hint?: string }) {
  const set = (i: number, patch: Partial<ExtraSection>) => onChange(value.map((s, n) => (n === i ? { ...s, ...patch } : s)));
  return (
    <div className="space-y-3">
      <div><p className="text-sm font-semibold">Extra sections</p><p className="text-xs text-mute">{hint ?? "Rules, prizes, schedule: anything people should know."}</p></div>
      {value.map((s, i) => (
        <div key={i} className="space-y-2 rounded-2xl bg-wash p-4">
          <div className="flex gap-2">
            <input className="field" placeholder="Title, e.g. Rules" maxLength={80} value={s.title} onChange={(e) => set(i, { title: e.target.value })} />
            <button type="button" aria-label="Remove section" onClick={() => onChange(value.filter((_, n) => n !== i))} className="rounded-xl px-3 text-mute hover:bg-black/5 hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
          </div>
          <textarea className="field min-h-24" placeholder="Details" maxLength={2000} value={s.body} onChange={(e) => set(i, { body: e.target.value })} />
        </div>
      ))}
      {value.length < MAX && <Button type="button" size="sm" variant="outline" onClick={() => onChange([...value, { title: "", body: "" }])}><Plus className="h-4 w-4" /> Add a section</Button>}
    </div>
  );
}
