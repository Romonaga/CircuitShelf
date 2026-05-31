import { useState } from "react";
import type { AIUsageBreakdown, AIUsageEvent } from "../types";
import { formatInteger, formatNumber } from "../lib/format";
import { useAIUsageReport } from "../hooks/useAIUsageReport";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";
import { Stat } from "./Stat";

function money(value: number | null | undefined): string {
  return `$${formatNumber(value ?? 0)}`;
}

function formatDate(value?: string | null): string {
  return value ? new Date(value).toLocaleString() : "n/a";
}

function BreakdownCards({ title, rows }: { title: string; rows: AIUsageBreakdown[] }) {
  return (
    <section className="ai-usage-breakdown">
      <h3>{title}</h3>
      <div className="ai-usage-card-grid">
        {rows.length ? rows.slice(0, 5).map((row) => (
          <div key={row.label} className="ai-usage-card">
            <span>{row.label}</span>
            <strong>{money(row.estimatedCost)}</strong>
            <small>{formatInteger(row.tokens)} tokens | {formatInteger(row.calls)} calls</small>
          </div>
        )) : <p className="empty-state">No usage in this range.</p>}
      </div>
    </section>
  );
}

function UsageEventsTable({ events }: { events: AIUsageEvent[] }) {
  return (
    <section className="performance-chart-card">
      <div className="performance-chart-heading">
        <div>
          <h3>Audited calls</h3>
          <p>Provider calls with token and cost accounting.</p>
        </div>
        <span>{formatInteger(events.length)} rows</span>
      </div>
      <div className="table-wrap">
        <table className="data-table ai-usage-table">
          <thead>
            <tr>
              <th>When</th>
              <th>User</th>
              <th>Paid by</th>
              <th>Task</th>
              <th>Round</th>
              <th>Model</th>
              <th>Tokens</th>
              <th>Cost</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {events.length ? events.map((event) => (
              <tr key={event.id}>
                <td>{formatDate(event.createdAt)}</td>
                <td>{event.username}</td>
                <td>{event.paidBy}</td>
                <td>{event.taskLabel}</td>
                <td>{event.roundNumber} / {event.roundCount}</td>
                <td>{event.modelName}</td>
                <td>{formatInteger(event.inputTokens + event.cachedInputTokens + event.outputTokens)}</td>
                <td>{money(event.estimatedCost)}</td>
                <td>{event.success ? "OK" : event.errorMessage || "Failed"}</td>
              </tr>
            )) : (
              <tr>
                <td colSpan={9}>No audited AI calls yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function AIUsageView({
  isActive,
  canManageSystem
}: {
  isActive: boolean;
  canManageSystem: boolean;
}) {
  const [scope, setScope] = useState<"entity" | "system">(canManageSystem ? "system" : "entity");
  const report = useAIUsageReport(isActive, scope);
  const summary = report.report?.summary;

  return (
    <section className="ai-usage-view">
      <SectionHeader
        title="AI usage"
        description={report.loading ? "Loading usage..." : "Token spend, budget context, and audited provider calls."}
        actions={
          <div className="performance-actions">
            {canManageSystem ? (
              <select value={scope} onChange={(event) => setScope(event.target.value as "entity" | "system")}>
                <option value="system">System</option>
                <option value="entity">Entity</option>
              </select>
            ) : null}
            <button className="ghost-button" onClick={() => void report.refresh()}>Refresh</button>
          </div>
        }
      />
      <ErrorMessage message={report.error} />
      <div className="status-grid performance-stats">
        <Stat label="Calls" value={formatInteger(summary?.calls)} />
        <Stat label="Successful" value={formatInteger(summary?.successfulCalls)} />
        <Stat label="Tokens" value={formatInteger(summary?.tokens)} />
        <Stat label="Output tokens" value={formatInteger(summary?.outputTokens)} />
        <Stat label="Cost" value={money(summary?.estimatedCost)} />
        <Stat label="Scope" value={scope} />
      </div>
      <div className="ai-usage-breakdown-grid">
        <BreakdownCards title="By task" rows={report.report?.byTask ?? []} />
        <BreakdownCards title="By user" rows={report.report?.byUser ?? []} />
        <BreakdownCards title="By payer" rows={report.report?.byPayer ?? []} />
        <BreakdownCards title="By model" rows={report.report?.byModel ?? []} />
      </div>
      <UsageEventsTable events={report.report?.events ?? []} />
    </section>
  );
}
