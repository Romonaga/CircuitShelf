import type { RuntimeBatches } from "../types";
import { formatInteger } from "../lib/format";

function BatchRow({
  label,
  batch
}: {
  label: string;
  batch?: RuntimeBatches[keyof RuntimeBatches];
}) {
  if (!batch) {
    return null;
  }
  return (
    <div className="batch-row">
      <div>
        <strong>{label}</strong>
        <p>{batch.model || "Model not configured"}</p>
      </div>
      <span><small>Active</small><b>{formatInteger(batch.active)}</b></span>
      <span><small>Configured</small><b>{formatInteger(batch.configured)}</b></span>
      <span><small>Recommended</small><b>{formatInteger(batch.recommended)}</b></span>
      <em>{batch.auto ? "auto" : "manual"}</em>
    </div>
  );
}

export function RuntimeBatchPanel({ batches }: { batches?: RuntimeBatches | null }) {
  return (
    <section className="performance-chart-card compact">
      <div className="performance-chart-heading">
        <div>
          <h3>GPU batch sizing</h3>
          <p>Runtime choices used by embedding and reranking work.</p>
        </div>
      </div>
      <div className="batch-table">
        <BatchRow label="Embedding" batch={batches?.embedding} />
        <BatchRow label="Reranker" batch={batches?.reranker} />
      </div>
    </section>
  );
}
