import { formatInteger } from "../../libs/format";
import { AI_USAGE_SCOPE_COPY } from "../../libs/aiUsageScopes";
import { money } from "../../libs/money";
import type { AIUsageScope } from "../../hooks/useAIUsageReport";
import type { AIUsageReport } from "../../types";

export function AIUsageSummary({ report, scope }: { report?: AIUsageReport | null; scope: AIUsageScope }) {
  const summary = report?.summary;
  const successRate = summary?.calls ? Math.round(((summary.successfulCalls || 0) / summary.calls) * 100) : 0;
  const inputTokens = (summary?.inputTokens ?? 0) + (summary?.cachedInputTokens ?? 0);
  const reconciledCalls = summary?.reconciledCalls ?? 0;
  return (
    <section className="ai-usage-hero">
      <div className="ai-usage-scope-card">
        <span>Current scope</span>
        <strong>{AI_USAGE_SCOPE_COPY[scope].label}</strong>
        <p>{AI_USAGE_SCOPE_COPY[scope].description}</p>
      </div>
      <div className="ai-usage-spend-card">
        <span>Estimated spend</span>
        <strong>{money(summary?.estimatedCost)}</strong>
        <div className="ai-usage-spend-meta">
          <span>{money(summary?.billableCost)} billable</span>
          <span>{formatInteger(summary?.calls)} calls</span>
          <span>{formatInteger(summary?.tokens)} total tokens</span>
          <span>{successRate}% successful</span>
        </div>
      </div>
      <div className="ai-usage-token-strip">
        <AIUsageMetric label="Input + cached" value={formatInteger(inputTokens)} />
        <AIUsageMetric label="Output" value={formatInteger(summary?.outputTokens)} />
        <AIUsageMetric label="Reconciled" value={formatInteger(reconciledCalls)} />
      </div>
    </section>
  );
}

function AIUsageMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
