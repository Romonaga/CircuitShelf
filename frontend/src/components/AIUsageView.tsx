import { useState } from "react";
import { downloadAIUsageCsv } from "../libs/api";
import { downloadBlob } from "../libs/download";
import { errorMessage } from "../libs/errors";
import { formatInteger } from "../libs/format";
import { money } from "../libs/money";
import { type AIUsageScope, useAIUsageReport } from "../hooks/useAIUsageReport";
import { AIUsageBreakdownCards } from "./AIUsageBreakdownCards";
import { AIUsageEventsTable } from "./AIUsageEventsTable";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";
import { Stat } from "./Stat";

export function AIUsageView({
  isActive,
  canManageEntity,
  canManageSystem
}: {
  isActive: boolean;
  canManageEntity: boolean;
  canManageSystem: boolean;
}) {
  const [scope, setScope] = useState<AIUsageScope>(canManageSystem ? "system" : canManageEntity ? "entity" : "personal");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const report = useAIUsageReport(isActive, scope);
  const summary = report.report?.summary;

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
              {canManageSystem ? (
                <>
                <option value="system">System</option>
                <option value="entity">Entity</option>
                </>
              ) : null}
              {!canManageSystem && canManageEntity ? <option value="entity">Entity</option> : null}
                <option value="personal">Personal</option>
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
      <div className="status-grid performance-stats">
        <Stat label="Calls" value={formatInteger(summary?.calls)} />
        <Stat label="Successful" value={formatInteger(summary?.successfulCalls)} />
        <Stat label="Tokens" value={formatInteger(summary?.tokens)} />
        <Stat label="Output tokens" value={formatInteger(summary?.outputTokens)} />
        <Stat label="Cost" value={money(summary?.estimatedCost)} />
        <Stat label="Scope" value={scope} />
      </div>
      <div className="ai-usage-breakdown-grid">
        <AIUsageBreakdownCards title="By task" rows={report.report?.byTask ?? []} />
        <AIUsageBreakdownCards title="By user" rows={report.report?.byUser ?? []} />
        <AIUsageBreakdownCards title="By payer" rows={report.report?.byPayer ?? []} />
        <AIUsageBreakdownCards title="By model" rows={report.report?.byModel ?? []} />
        <AIUsageBreakdownCards title="By context" rows={report.report?.byContext ?? []} />
      </div>
      <AIUsageEventsTable events={report.report?.events ?? []} />
    </section>
  );
}
