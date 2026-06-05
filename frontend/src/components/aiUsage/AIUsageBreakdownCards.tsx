import type { AIUsageBreakdown } from "../../types";
import { formatInteger } from "../../libs/format";
import { money } from "../../libs/money";

export function AIUsageBreakdownCards({
  title,
  rows,
  compact = false
}: {
  title: string;
  rows: AIUsageBreakdown[];
  compact?: boolean;
}) {
  return (
    <section className={compact ? "ai-usage-breakdown compact" : "ai-usage-breakdown"}>
      <h3>{title}</h3>
      <div className="ai-usage-card-grid">
        {rows.length ? rows.slice(0, 5).map((row) => (
          <div key={row.label} className="ai-usage-card">
            <div>
              <span>{row.label}</span>
              <small>{formatInteger(row.tokens)} tokens | {formatInteger(row.calls)} calls</small>
            </div>
            <strong>{money(row.estimatedCost)}</strong>
          </div>
        )) : <p className="empty-state">No usage in this range.</p>}
      </div>
    </section>
  );
}
