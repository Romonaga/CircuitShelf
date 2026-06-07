import type { IngestStatus, IngestWorkerBudget, RuntimeBatches } from "../types";
import { activeFileRows } from "../libs/ingest/format";
import { IngestChangeSummary } from "./ingest/IngestChangeSummary";
import { IngestDetailGrid } from "./ingest/IngestDetailGrid";
import { IngestFileProgressTable } from "./ingest/IngestFileProgressTable";
import { IngestQueueSummary } from "./ingest/IngestQueueSummary";
import { IngestStatusHeader } from "./ingest/IngestStatusHeader";
import { IngestWorkerBudgetPanel } from "./ingest/IngestWorkerBudgetPanel";

export function IngestStatusPanel({
  ingest,
  workerBudget,
  runtimeBatches,
  pendingReview,
  onOpenReview,
  display = "standard"
}: {
  ingest?: IngestStatus | null;
  workerBudget?: IngestWorkerBudget | null;
  runtimeBatches?: RuntimeBatches | null;
  pendingReview?: number;
  onOpenReview?: () => void;
  display?: "standard" | "expanded";
}) {
  if (!ingest) {
    return null;
  }

  const pending = pendingReview ?? 0;
  const isRunning = Boolean(ingest.running);
  const hasError = Boolean(ingest.lastError);
  const totalFiles = ingest.totalFiles ?? 0;
  const processedFiles = ingest.processedFiles ?? 0;
  const fileRows = activeFileRows(ingest);
  const className = [
    "ingest-status-panel",
    display === "expanded" ? "expanded" : "",
    fileRows.length ? "with-file-progress" : "",
    hasError ? "error" : isRunning ? "running" : ""
  ].filter(Boolean).join(" ");

  return (
    <div className={className}>
      <IngestStatusHeader running={isRunning} pendingReview={pending} reason={ingest.lastReason} onOpenReview={onOpenReview} />
      <IngestDetailGrid ingest={ingest} />
      <IngestWorkerBudgetPanel workerBudget={workerBudget} runtimeBatches={runtimeBatches} />
      <IngestQueueSummary
        running={isRunning}
        totalFiles={totalFiles}
        processedFiles={processedFiles}
        indexedDocuments={Number(ingest.details?.completedDocuments ?? 0)}
        failedDocuments={Number(ingest.details?.failedDocuments ?? 0)}
        queuedSaveDocuments={Number(ingest.details?.queuedSaveDocuments ?? 0)}
        trackedFiles={fileRows.length}
      />
      <IngestFileProgressTable running={isRunning} rows={fileRows} />
      <IngestChangeSummary changes={ingest.lastChanges} />
      {hasError ? <p className="ingest-error">{ingest.lastError}</p> : null}
    </div>
  );
}
