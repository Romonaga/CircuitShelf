import type { IngestStatus } from "../../types";
import { formatInteger } from "../../libs/format";
import { formatDateTime, formatDetailLabel, formatDetailValue, formatStage } from "../../libs/ingest/format";

export function IngestDetailGrid({ ingest }: { ingest: IngestStatus }) {
  const totalFiles = ingest.totalFiles ?? 0;
  const processedFiles = ingest.processedFiles ?? 0;
  const details = Object.entries(ingest.details ?? {}).filter(([, value]) => value !== undefined);

  return (
    <div className="ingest-status-grid">
      <span>Stage: {formatStage(ingest.stage)}</span>
      {ingest.running && totalFiles ? <span>Progress: {formatInteger(processedFiles)} / {formatInteger(totalFiles)} files</span> : null}
      {details.map(([key, value]) => (
        <span key={key}>{formatDetailLabel(key)}: {formatDetailValue(value)}</span>
      ))}
      <span>Started: {formatDateTime(ingest.lastStartedAt)}</span>
      <span>Finished: {formatDateTime(ingest.lastFinishedAt)}</span>
      <span>Result: {ingest.lastResult || "waiting"}</span>
      <span>Next check: {formatDateTime(ingest.nextCheckAt)}</span>
    </div>
  );
}
