import type { AIUsageEvent } from "../types";
import { formatInteger } from "../libs/format";
import { money } from "../libs/money";

function formatDate(value?: string | null): string {
  return value ? new Date(value).toLocaleString() : "n/a";
}

function costLabel(event: AIUsageEvent): string {
  if (event.finalCost !== null && event.finalCost !== undefined) {
    return `${money(event.finalCost)} final`;
  }
  return `${money(event.estimatedCost)} est.`;
}

function statusLabel(event: AIUsageEvent): string {
  const costStatus = event.costStatus && event.costStatus !== "estimated" ? ` / ${event.costStatus}` : "";
  return `${event.success ? "OK" : event.errorMessage || "Failed"}${costStatus}`;
}

export function AIUsageEventsTable({ events }: { events: AIUsageEvent[] }) {
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
              <th>Why</th>
              <th>Time</th>
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
                <td className="usage-reason">{event.decisionReason || event.contextType || "n/a"}</td>
                <td>{event.latencyMs ? `${(event.latencyMs / 1000).toFixed(2)}s` : "n/a"}</td>
                <td>{formatInteger(event.inputTokens + event.cachedInputTokens + event.outputTokens)}</td>
                <td>{costLabel(event)}</td>
                <td>{statusLabel(event)}</td>
              </tr>
            )) : (
              <tr>
                <td colSpan={11}>No audited AI calls yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
