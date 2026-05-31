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

export function RecentWorkTable({ rows }: { rows: PerformanceWorkRun[] }) {
  return (
    <section className="performance-chart-card">
      <div className="performance-chart-heading">
        <div>
          <h3>Recent work</h3>
          <p>Completed checks, document ingestion runs, and other measured work.</p>
        </div>
        <span>{formatInteger(rows.length)} rows</span>
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
                <td>{row.triggerReason || "n/a"}</td>
                <td>{formatDuration(row.durationMs)}</td>
                <td>{formatInteger(row.chunks)}</td>
                <td>{formatInteger(row.images)}</td>
              </tr>
            )) : (
              <tr>
                <td colSpan={7}>No persisted work history yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
