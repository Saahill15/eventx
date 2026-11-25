"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FinanceCategory, FinanceSummary } from "@/lib/types";
import { BudgetPanel, IncomePanel, OverviewPanel, SettingsPanel, type Section } from "./FinancePanels";
import { SpendingPanel } from "./FinanceSpend";
import { PaymentsAdmin } from "./PaymentsAdmin";
import { SubTabs } from "@/components/ui/SubTabs";

const SECTIONS: { id: Section; label: string }[] = [{ id: "overview", label: "Overview" }, { id: "spending", label: "Spending" }, { id: "budget", label: "Budget" }, { id: "income", label: "Income" }, { id: "payments", label: "Online payments" }, { id: "settings", label: "Settings" }];

/**
 * The fest's money: the budget, requests to spend with approvals, money coming in from sponsors and others, and where it all
 * stands. The director and core team run it; everyone on the committee can ask to spend.
 */
export function FinanceTab({ slug }: { slug: string }) {
  const [section, setSection] = useState<Section>("overview");
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [cats, setCats] = useState<FinanceCategory[]>([]);
  const reload = useCallback(() => {
    api<FinanceSummary>(`/api/fests/${slug}/finance/summary`).then(setSummary).catch(() => {});
    api<FinanceCategory[]>(`/api/fests/${slug}/finance/categories`).then(setCats).catch(() => {});
  }, [slug]);
  useEffect(() => { reload(); }, [reload]);
  const waiting = summary?.pending_requests ?? 0;
  return (
    <div className="space-y-6">
      <SubTabs label="Finance sections" value={section} onChange={setSection} items={SECTIONS.map((x) => ({ id: x.id, label: x.label, badge: x.id === "spending" ? waiting : 0 }))} />
      {section === "overview" && <OverviewPanel slug={slug} summary={summary} go={setSection} />}
      {section === "spending" && <SpendingPanel slug={slug} onChanged={reload} />}
      {section === "budget" && <BudgetPanel slug={slug} cats={cats} reloadAll={reload} go={setSection} />}
      {section === "income" && <IncomePanel slug={slug} cats={cats} summary={summary} reloadAll={reload} go={setSection} />}
      {section === "payments" && <PaymentsAdmin slug={slug} />}
      {section === "settings" && <SettingsPanel slug={slug} cats={cats} reloadAll={reload} />}
    </div>
  );
}
