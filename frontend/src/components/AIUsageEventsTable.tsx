import type { AIUsageEvent } from "../types";
import { formatInteger } from "../libs/format";
import { money } from "../libs/money";

function formatDate(value?: string | null): string {
  return value ? new Date(value).toLocaleString() : "n/a";
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
                <td>{money(event.estimatedCost)}</td>
                <td>{event.success ? "OK" : event.errorMessage || "Failed"}</td>
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
