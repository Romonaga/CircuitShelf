import type { PerformanceWorkRun } from "../types";
import { formatDurationMs, formatInteger } from "../libs/format";
import { chartColors } from "../libs/chartColors";

interface WorkSummary {
  key: string;
  label: string;
  count: number;
  averageMs: number;
  failures: number;
}

function summarize(rows: PerformanceWorkRun[]): WorkSummary[] {
  const grouped = new Map<string, { label: string; count: number; totalMs: number; failures: number }>();
  rows.forEach((row) => {
    const key = row.workType || "unknown";
    const current = grouped.get(key) ?? { label: row.workTypeLabel || key, count: 0, totalMs: 0, failures: 0 };
    current.count += 1;
    current.totalMs += Math.max(0, row.durationMs || 0);
    if (row.status && row.status !== "completed" && row.status !== "skipped") {
      current.failures += 1;
    }
    grouped.set(key, current);
  });
  return Array.from(grouped.entries())
    .map(([key, value]) => ({
      key,
      label: value.label,
      count: value.count,
      failures: value.failures,
      averageMs: value.count ? value.totalMs / value.count : 0
    }))
    .sort((left, right) => right.averageMs - left.averageMs)
    .slice(0, 8);
}

export function WorkDurationChart({ rows }: { rows: PerformanceWorkRun[] }) {
  const data = summarize(rows);
  const max = Math.max(1, ...data.map((row) => row.averageMs));
  return (
    <section className="performance-chart-card work-chart-card">
      <div className="performance-chart-heading">
        <div>
          <h3>Work duration by type</h3>
          <p>Average duration for recent background and AI work.</p>
        </div>
        <span>{formatInteger(rows.length)} runs</span>
      </div>
      {data.length ? (
        <div className="work-bars">
          {data.map((row, index) => (
            <div key={row.key} className="work-bar-row">
              <div>
                <strong>{row.label}</strong>
                <small>{formatInteger(row.count)} runs{row.failures ? ` | ${row.failures} failed` : ""}</small>
              </div>
              <div className="work-bar-track">
                <span
                  style={{
                    width: `${Math.max(3, (row.averageMs / max) * 100)}%`,
                    background: Object.values(chartColors)[index % Object.values(chartColors).length]
                  }}
                />
              </div>
              <b>{formatDurationMs(row.averageMs)}</b>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty-state">No recent work runs have been recorded.</p>
      )}
    </section>
  );
}
