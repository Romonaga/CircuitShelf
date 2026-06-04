import { formatInteger } from "../../lib/format";

export function IngestQueueSummary({
  running,
  totalFiles,
  processedFiles,
  indexedDocuments,
  failedDocuments,
  queuedSaveDocuments,
  trackedFiles
}: {
  running: boolean;
  totalFiles: number;
  processedFiles: number;
  indexedDocuments: number;
  failedDocuments: number;
  queuedSaveDocuments: number;
  trackedFiles: number;
}) {
  if (!running || !totalFiles) {
    return null;
  }

  const notStartedFiles = Math.max(totalFiles - processedFiles - trackedFiles, 0);

  return (
    <div className="ingest-queue-summary">
      <span><small>Processed</small><strong>{formatInteger(processedFiles)}</strong></span>
      <span><small>Indexed</small><strong>{formatInteger(indexedDocuments)}</strong></span>
      <span><small>Failed</small><strong>{formatInteger(failedDocuments)}</strong></span>
      <span><small>DB queue</small><strong>{formatInteger(queuedSaveDocuments)}</strong></span>
      <span><small>Active</small><strong>{formatInteger(trackedFiles)}</strong></span>
      <span><small>Not started</small><strong>{formatInteger(notStartedFiles)}</strong></span>
      <span><small>Total</small><strong>{formatInteger(totalFiles)}</strong></span>
    </div>
  );
}
