import { money } from "../../libs/money";
import type { AIUsageCostPoint, AIUsageReport } from "../../types";

function dateLabel(value: string): string {
  if (!value) {
    return "n/a";
  }
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function maxCost(points: AIUsageCostPoint[]): number {
  return Math.max(
    0,
    ...points.flatMap((point) => [point.estimatedCost, point.actualCost, point.verifiedCost])
  );
}

function barWidth(value: number, max: number): string {
  if (max <= 0) {
    return "0%";
  }
  return `${Math.max(2, Math.min(100, (value / max) * 100))}%`;
}

export function AIUsageCostGraph({ report }: { report?: AIUsageReport | null }) {
  const points = report?.costTimeline ?? [];
  const max = maxCost(points);
  const summary = report?.summary;
  const delta = (summary?.actualCost ?? summary?.billableCost ?? 0) - (summary?.estimatedCost ?? 0);

  return (
    <section className="performance-chart-card ai-cost-graph">
      <div className="performance-chart-heading">
        <div>
          <h3>Cost comparison</h3>
          <p>Estimated, actual, and verified OpenAI costs for the selected window.</p>
        </div>
        <span>{money(delta)} delta</span>
      </div>
      <div className="ai-cost-legend" aria-label="Cost comparison legend">
        <span><i className="estimated" /> Estimated</span>
        <span><i className="actual" /> Actual</span>
        <span><i className="verified" /> Verified</span>
      </div>
      {points.length ? (
        <div className="ai-cost-bars">
          {points.map((point) => (
            <div className="ai-cost-row" key={point.date}>
              <strong>{dateLabel(point.date)}</strong>
              <div className="ai-cost-bar-stack">
                <CostBar label="Estimated" value={point.estimatedCost} max={max} tone="estimated" />
                <CostBar label="Actual" value={point.actualCost} max={max} tone="actual" />
                <CostBar label="Verified" value={point.verifiedCost} max={max} tone="verified" />
              </div>
              <small>{point.reconciledCalls} / {point.calls} reconciled</small>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty-state">No AI usage costs in this window.</p>
      )}
    </section>
  );
}

function CostBar({
  label,
  value,
  max,
  tone
}: {
  label: string;
  value: number;
  max: number;
  tone: "estimated" | "actual" | "verified";
}) {
  return (
    <div className="ai-cost-bar-line">
      <span>{label}</span>
      <div className="ai-cost-bar-track">
        <b className={tone} style={{ width: barWidth(value, max) }} />
      </div>
      <em>{money(value)}</em>
    </div>
  );
}
