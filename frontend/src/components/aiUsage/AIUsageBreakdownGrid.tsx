import type { AIUsageReport } from "../../types";
import { AIUsageBreakdownCards } from "./AIUsageBreakdownCards";

export function AIUsageBreakdownGrid({ report }: { report?: AIUsageReport | null }) {
  return (
    <div className="ai-usage-breakdown-layout">
      <div className="ai-usage-breakdown-primary">
        <AIUsageBreakdownCards title="Spend by task" rows={report?.byTask ?? []} compact />
        <AIUsageBreakdownCards title="Spend by payer" rows={report?.byPayer ?? []} compact />
      </div>
      <div className="ai-usage-breakdown-secondary">
        <AIUsageBreakdownCards title="Users" rows={report?.byUser ?? []} compact />
        <AIUsageBreakdownCards title="Models" rows={report?.byModel ?? []} compact />
        <AIUsageBreakdownCards title="Contexts" rows={report?.byContext ?? []} compact />
      </div>
    </div>
  );
}
