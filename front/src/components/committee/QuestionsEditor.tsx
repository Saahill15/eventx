"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";

export interface QuestionDraft { id?: number; label: string; kind: "short_text" | "choice" | "yes_no"; required: boolean; options: string }

const KINDS = { short_text: "Short answer", choice: "Pick one", yes_no: "Yes or no" } as const;
const MAX = 10;

export const toDraft = (q: { id: number; label: string; kind: QuestionDraft["kind"]; required: boolean; options: string[] | null }): QuestionDraft => ({ id: q.id, label: q.label, kind: q.kind, required: q.required, options: (q.options ?? []).join(", ") });
export const toQuestionPayload = (qs: QuestionDraft[]) => qs.filter((q) => q.label.trim()).map((q) => ({
  ...(q.id ? { id: q.id } : {}), label: q.label.trim(), kind: q.kind, required: q.required,
  options: q.kind === "choice" ? q.options.split(",").map((o) => o.trim()).filter(Boolean) : null,
}));

/** Extra questions students answer when they register, such as T-shirt size or team name. */
export function QuestionsEditor({ value, onChange, locked }: { value: QuestionDraft[]; onChange: (v: QuestionDraft[]) => void; locked: boolean }) {
  const set = (i: number, patch: Partial<QuestionDraft>) => onChange(value.map((q, n) => (n === i ? { ...q, ...patch } : q)));
  return (
    <div className="space-y-3">
      <div><p className="text-sm font-semibold">Questions for students</p><p className="text-xs text-mute">{locked ? "People have registered, so existing questions are fixed. You can add new optional ones." : "Asked when someone registers. Up to 10."}</p></div>
      {value.map((q, i) => {
        const fixed = locked && q.id !== undefined;
        return (
          <div key={q.id ?? `new-${i}`} className="space-y-2 rounded-2xl bg-wash p-4">
            <div className="flex gap-2">
              <input className="field" placeholder="Question, e.g. Team name" maxLength={200} value={q.label} disabled={fixed} onChange={(e) => set(i, { label: e.target.value })} />
              {!fixed && <button type="button" aria-label="Remove question" onClick={() => onChange(value.filter((_, n) => n !== i))} className="rounded-xl px-3 text-mute hover:bg-black/5 hover:text-red-600"><Trash2 className="h-4 w-4" /></button>}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <select className="field w-auto" value={q.kind} disabled={fixed} onChange={(e) => set(i, { kind: e.target.value as QuestionDraft["kind"] })}>{Object.entries(KINDS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-[#111]" checked={q.required} disabled={fixed || (locked && q.id === undefined)} onChange={(e) => set(i, { required: e.target.checked })} /> Required</label>
            </div>
            {q.kind === "choice" && <input className="field" placeholder="Options, separated by commas: S, M, L, XL" disabled={fixed} value={q.options} onChange={(e) => set(i, { options: e.target.value })} />}
          </div>
        );
      })}
      {value.length < MAX && <Button type="button" size="sm" variant="outline" onClick={() => onChange([...value, { label: "", kind: "short_text", required: false, options: "" }])}><Plus className="h-4 w-4" /> Add a question</Button>}
    </div>
  );
}
