import type { IngestWorkerBudget, RuntimeBatches } from "../../types";
import { formatInteger } from "../../libs/format";
import { batchBrief, batchSummary } from "../../libs/ingest/format";

export function IngestWorkerBudgetPanel({
  workerBudget,
  runtimeBatches
}: {
  workerBudget?: IngestWorkerBudget | null;
  runtimeBatches?: RuntimeBatches | null;
}) {
  if (!workerBudget) {
    return null;
  }

  return (
    <div className="ingest-worker-budget">
      <span><small>Cores</small><strong>{formatInteger(workerBudget.cpuCores)}</strong></span>
      <span><small>Reserved</small><strong>{formatInteger(workerBudget.reservedCores)}</strong></span>
      <span><small>Usable</small><strong>{formatInteger(workerBudget.usableCores)}</strong></span>
      <span>
        <small>Worker slots</small>
        <strong>
          {formatInteger(workerBudget.activeDocumentWorkers)} / {formatInteger(workerBudget.documentWorkerCapacity ?? workerBudget.activeDocumentWorkers)}
        </strong>
      </span>
      <span><small>Embed CUDA</small><strong title={batchSummary(runtimeBatches?.embedding)}>{batchBrief(runtimeBatches?.embedding)}</strong></span>
      <span><small>Rerank CUDA</small><strong title={batchSummary(runtimeBatches?.reranker)}>{batchBrief(runtimeBatches?.reranker)}</strong></span>
    </div>
  );
}
