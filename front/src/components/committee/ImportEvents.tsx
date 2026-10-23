"use client";

import { useRef, useState } from "react";
import { Download, FileUp } from "lucide-react";
import { downloadFile, postFile } from "@/lib/api";
import type { ImportResult } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Notice } from "@/components/ui/bits";

/** Add many events at once from a spreadsheet saved as CSV: check the file first, then import every row or none. */
export function ImportEvents({ slug, onDone, onClose }: { slug: string; onDone: () => void; onClose: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const send = async (f: File, dryRun: boolean) => {
    setBusy(true); setError("");
    try {
      const r = await postFile<ImportResult>(`/api/fests/${slug}/events/import?dry_run=${dryRun}`, f);
      setResult(r);
      if (r.created > 0) onDone();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not read the file."); }
    setBusy(false);
  };
  const pick = (f: File | undefined) => { if (!f) return; setFile(f); setResult(null); send(f, true); };
  const template = async () => { try { await downloadFile(`/api/fests/${slug}/events/import-template`, "hiveout-events-template.csv"); } catch (e) { setError(e instanceof Error ? e.message : "Could not download."); } };

  const problems = result?.rows.filter((r) => r.errors.length > 0) ?? [];
  const ready = !!result && result.file_errors.length === 0 && problems.length === 0 && result.valid > 0 && result.created === 0;

  return (
    <div className="card max-w-4xl space-y-5 p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-bold tracking-tight">Import events from a spreadsheet</h2>
          <p className="mt-1 text-sm text-mute">Fill in the template in Excel or Google Sheets, save it as CSV, and upload it. Nothing is added until every row is right.</p>
        </div>
        <Button size="sm" variant="ghost" onClick={onClose}>Close</Button>
      </div>
      <ErrorNote>{error}</ErrorNote>

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={template}><Download className="h-4 w-4" /> Download the template</Button>
        <Button onClick={() => input.current?.click()} disabled={busy}><FileUp className="h-4 w-4" /> {file ? "Choose another file" : "Choose your CSV file"}</Button>
        <input ref={input} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
      </div>
      {busy && <p className="text-sm text-mute">Checking {file?.name}…</p>}

      {result && result.created > 0 && <Notice tone="ok">Added {result.created} event{result.created === 1 ? "" : "s"} to your fest.</Notice>}
      {result && result.file_errors.length > 0 && <ErrorNote>{result.file_errors.join(" ")}</ErrorNote>}

      {result && result.rows.length > 0 && result.created === 0 && (
        <>
          <p className="text-sm font-semibold">{problems.length === 0 ? `All ${result.valid} rows look right.` : `${problems.length} of ${result.rows.length} rows need fixing. Fix them in your spreadsheet and upload it again.`}</p>
          <div className="max-h-96 overflow-auto rounded-2xl ring-1 ring-black/5">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-wash text-xs uppercase tracking-wider text-mute"><tr><th className="px-4 py-2">Row</th><th className="px-4 py-2">Event</th><th className="px-4 py-2">Problems</th></tr></thead>
              <tbody className="divide-y divide-black/5">
                {result.rows.map((r) => (
                  <tr key={r.line} className={r.errors.length ? "bg-red-50/60" : ""}>
                    <td className="px-4 py-2 text-mute">{r.line}</td>
                    <td className="px-4 py-2 font-medium">{r.title || "—"}</td>
                    <td className="px-4 py-2">{r.errors.length ? <ul className="list-disc pl-4 text-red-700">{r.errors.map((e) => <li key={e}>{e}</li>)}</ul> : <span className="text-emerald-700">OK</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {ready && file && <Button size="lg" disabled={busy} onClick={() => send(file, false)}>Add {result.valid} event{result.valid === 1 ? "" : "s"}</Button>}
        </>
      )}
    </div>
  );
}
