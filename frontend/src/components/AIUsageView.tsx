import { useState } from "react";
import { downloadAIUsageCsv } from "../libs/api";
import { allowedAIUsageScopes, AI_USAGE_SCOPE_COPY, defaultAIUsageScope } from "../libs/aiUsageScopes";
import { downloadBlob } from "../libs/download";
import { errorMessage } from "../libs/errors";
import { type AIUsageScope, useAIUsageReport } from "../hooks/useAIUsageReport";
import { AIUsageBreakdownGrid } from "./aiUsage/AIUsageBreakdownGrid";
import { AIUsageCostGraph } from "./aiUsage/AIUsageCostGraph";
import { AIUsageSummary } from "./aiUsage/AIUsageSummary";
import { AIUsageEventsTable } from "./AIUsageEventsTable";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";

export function AIUsageView({
  isActive,
  canManageEntity,
  canManageSystem
}: {
  isActive: boolean;
  canManageEntity: boolean;
  canManageSystem: boolean;
}) {
  const [scope, setScope] = useState<AIUsageScope>(defaultAIUsageScope(canManageSystem, canManageEntity));
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const report = useAIUsageReport(isActive, scope);
  const scopeOptions = allowedAIUsageScopes(canManageSystem, canManageEntity);

  async function exportCsv() {
    setExporting(true);
    setExportError("");
    try {
      const blob = await downloadAIUsageCsv(scope);
      const stamp = new Date().toISOString().slice(0, 10);
      downloadBlob(blob, `circuit-shelf-${scope}-ai-usage-${stamp}.csv`);
    } catch (err) {
      setExportError(errorMessage(err, "Could not export AI usage"));
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="ai-usage-view">
      <SectionHeader
        title="AI usage"
        description={report.loading ? "Loading usage..." : "Token spend, budget context, and audited provider calls."}
        actions={
          <div className="performance-actions">
            <select value={scope} onChange={(event) => setScope(event.target.value as AIUsageScope)}>
              {scopeOptions.map((option) => (
                <option key={option} value={option}>{AI_USAGE_SCOPE_COPY[option].label}</option>
              ))}
            </select>
            <button className="ghost-button" onClick={() => void exportCsv()} disabled={exporting}>
              {exporting ? "Exporting..." : "Export CSV"}
            </button>
            <button className="ghost-button" onClick={() => void report.refresh()}>Refresh</button>
          </div>
        }
      />
      <ErrorMessage message={report.error} />
      <ErrorMessage message={exportError} />
      <AIUsageSummary report={report.report} scope={scope} />
      <AIUsageCostGraph report={report.report} />
      <AIUsageBreakdownGrid report={report.report} />
      <AIUsageEventsTable events={report.report?.events ?? []} />
    </section>
  );
}
