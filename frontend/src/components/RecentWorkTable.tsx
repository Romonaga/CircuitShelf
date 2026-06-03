import type { PerformanceWorkRun } from "../types";
import { formatInteger, formatNumber } from "../lib/format";

function formatDuration(ms: number): string {
  if (!ms) {
    return "n/a";
  }
  if (ms < 1000) {
    return `${formatInteger(ms)} ms`;
  }
  const seconds = ms / 1000;
  if (seconds < 60) {
    return `${formatNumber(seconds)} sec`;
  }
  return `${formatNumber(seconds / 60)} min`;
}

function formatDate(value?: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toLocaleString();
}

function formatMoney(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return "n/a";
  }
  return `$${value.toFixed(value < 0.01 ? 4 : 2)}`;
}

function formatRounds(row: PerformanceWorkRun): string {
  if (!row.roundNumber && !row.roundCount) {
    return "n/a";
  }
  return `${row.roundNumber ?? 1} / ${row.roundCount ?? 1}`;
}

export function RecentWorkTable({
  rows,
  showIndexChecks,
  onShowIndexChecksChange
}: {
  rows: PerformanceWorkRun[];
  showIndexChecks: boolean;
  onShowIndexChecksChange: (value: boolean) => void;
}) {
  return (
    <section className="performance-chart-card">
      <div className="performance-chart-heading">
        <div>
          <h3>Recent work</h3>
          <p>Completed checks, document ingestion runs, and other measured work.</p>
        </div>
        <div className="performance-heading-actions">
          <label className="inline-checkbox">
            <input
              type="checkbox"
              checked={showIndexChecks}
              onChange={(event) => onShowIndexChecksChange(event.target.checked)}
            />
            Show index checks
          </label>
          <span>{formatInteger(rows.length)} rows</span>
        </div>
      </div>
      <div className="table-wrap">
        <table className="data-table performance-work-table">
          <thead>
            <tr>
              <th>When</th>
              <th>Type</th>
              <th>Status</th>
              <th>Reason</th>
              <th>Duration</th>
              <th>Chunks</th>
              <th>Images</th>
              <th>Tokens</th>
              <th>Cost</th>
              <th>Rounds</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr key={row.id}>
                <td>{formatDate(row.startedAt)}</td>
                <td>
                  <strong>{row.workTypeLabel}</strong>
                  {row.label ? <small>{row.label}</small> : null}
                </td>
                <td>{row.status}</td>
                <td>
                  {row.triggerReason || "n/a"}
                  {row.modelName ? <small>{row.modelName}</small> : null}
                  {row.paidBy ? <small>Paid by {row.paidBy}</small> : null}
                </td>
                <td>{formatDuration(row.durationMs)}</td>
                <td>{formatInteger(row.chunks)}</td>
                <td>{formatInteger(row.images)}</td>
                <td>{row.tokens ? formatInteger(row.tokens) : "n/a"}</td>
                <td>{formatMoney(row.estimatedCost)}</td>
                <td>{formatRounds(row)}</td>
              </tr>
            )) : (
              <tr>
                <td colSpan={10}>No persisted work history yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
