import type { PerformanceWorkRun } from "../../types";
import { formatInteger } from "../../libs/format";
import { chartColors } from "../../libs/chartColors";

function classify(row: PerformanceWorkRun) {
  if (row.status === "completed") {
    return "Completed";
  }
  if (row.status === "skipped") {
    return "Skipped";
  }
  if (row.status === "failed" || row.errorMessage) {
    return "Failed";
  }
  return "Other";
}

export function IngestionOutcomeGraph({ rows }: { rows: PerformanceWorkRun[] }) {
  const counts = rows.reduce<Record<string, number>>((acc, row) => {
    const label = classify(row);
    acc[label] = (acc[label] ?? 0) + 1;
    return acc;
  }, {});
  const items = [
    { label: "Completed", color: chartColors.green },
    { label: "Skipped", color: chartColors.blue },
    { label: "Failed", color: chartColors.vermillion },
    { label: "Other", color: chartColors.purple },
  ].map((item) => ({ ...item, count: counts[item.label] ?? 0 }));
  const total = items.reduce((sum, item) => sum + item.count, 0);

  return (
    <section className="performance-chart-card work-chart-card">
      <div className="performance-chart-heading">
        <div>
          <h3>Ingestion outcome mix</h3>
          <p>Recent work split by completed, skipped, failed, and other states.</p>
        </div>
        <span>{formatInteger(total)} runs</span>
      </div>
      {total ? (
        <div className="outcome-mix">
          <div className="outcome-stack" aria-label="Ingestion outcomes">
            {items.filter((item) => item.count > 0).map((item) => (
              <span
                key={item.label}
                style={{ width: `${(item.count / total) * 100}%`, background: item.color }}
                title={`${item.label}: ${formatInteger(item.count)}`}
              />
            ))}
          </div>
          <div className="outcome-legend">
            {items.map((item) => (
              <span key={item.label}>
                <i style={{ background: item.color }} />
                {item.label}
                <strong>{formatInteger(item.count)}</strong>
              </span>
            ))}
          </div>
        </div>
      ) : (
        <p className="empty-state">No work outcomes have been recorded for this range.</p>
      )}
    </section>
  );
}
