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

function patternFor(color: string, pattern: "solid" | "stripe" | "dot" | "cross") {
  if (pattern === "stripe") {
    return `repeating-linear-gradient(135deg, ${color} 0 8px, color-mix(in srgb, ${color} 62%, #000) 8px 12px)`;
  }
  if (pattern === "dot") {
    return `radial-gradient(circle at 4px 4px, color-mix(in srgb, ${color} 48%, #000) 0 2px, transparent 2px 8px), ${color}`;
  }
  if (pattern === "cross") {
    return `repeating-linear-gradient(45deg, transparent 0 7px, color-mix(in srgb, ${color} 52%, #000) 7px 9px), repeating-linear-gradient(-45deg, ${color} 0 7px, color-mix(in srgb, ${color} 72%, #000) 7px 9px)`;
  }
  return color;
}

export function IngestionOutcomeGraph({ rows }: { rows: PerformanceWorkRun[] }) {
  const counts = rows.reduce<Record<string, number>>((acc, row) => {
    const label = classify(row);
    acc[label] = (acc[label] ?? 0) + 1;
    return acc;
  }, {});
  const items = [
    { label: "Completed", color: chartColors.green, pattern: "solid" as const },
    { label: "Skipped", color: chartColors.blue, pattern: "stripe" as const },
    { label: "Failed", color: chartColors.vermillion, pattern: "cross" as const },
    { label: "Other", color: chartColors.purple, pattern: "dot" as const },
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
                style={{ width: `${(item.count / total) * 100}%`, background: patternFor(item.color, item.pattern) }}
                title={`${item.label}: ${formatInteger(item.count)}`}
              />
            ))}
          </div>
          <div className="outcome-legend">
            {items.map((item) => (
              <span key={item.label}>
                <i style={{ background: patternFor(item.color, item.pattern) }} />
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
