import type { AIUsageBreakdown } from "../types";
import { formatInteger } from "../lib/format";
import { money } from "../lib/money";

export function AIUsageBreakdownCards({ title, rows }: { title: string; rows: AIUsageBreakdown[] }) {
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
