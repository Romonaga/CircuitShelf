import type { IngestStatus } from "../types";
import { formatInteger } from "../lib/format";

function formatDateTime(value?: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toLocaleString();
}

function formatReason(reason?: string | null): string {
  if (!reason) {
    return "No indexing job has run yet.";
  }
  if (reason.startsWith("upload:")) {
    return `Upload: ${reason.slice("upload:".length)}`;
  }
  if (reason === "manual") {
    return "Manual check";
  }
  if (reason === "watch") {
    return "Background watcher";
  }
  return reason;
}

export function IngestStatusPanel({
  ingest,
  pendingReview,
  onOpenReview
}: {
  ingest?: IngestStatus | null;
  pendingReview?: number;
  onOpenReview?: () => void;
}) {
  if (!ingest) {
    return null;
  }

  const changes = ingest.lastChanges;
  const pending = pendingReview ?? 0;
  const isRunning = Boolean(ingest.running);
  const hasError = Boolean(ingest.lastError);

  return (
    <div className={hasError ? "ingest-status-panel error" : isRunning ? "ingest-status-panel running" : "ingest-status-panel"}>
      <div className="ingest-status-heading">
        <div>
          <strong>{isRunning ? "Indexing documents..." : pending ? "Documents ready for review" : "Indexing idle"}</strong>
          <p>{formatReason(ingest.lastReason)}</p>
        </div>
        {pending && onOpenReview ? (
          <button className="ghost-button" type="button" onClick={onOpenReview}>
            Open Review ({formatInteger(pending)})
          </button>
        ) : null}
      </div>
      <div className="ingest-status-grid">
        <span>Started: {formatDateTime(ingest.lastStartedAt)}</span>
        <span>Finished: {formatDateTime(ingest.lastFinishedAt)}</span>
        <span>Result: {ingest.lastResult || "waiting"}</span>
        <span>Next check: {formatDateTime(ingest.nextCheckAt)}</span>
      </div>
      {changes ? (
        <div className="ingest-change-list">
          <span>Added {formatInteger(changes.added)}</span>
          <span>Modified {formatInteger(changes.modified)}</span>
          <span>Removed {formatInteger(changes.removed)}</span>
          <span>Unchanged {formatInteger(changes.unchanged)}</span>
        </div>
      ) : null}
      {hasError ? <p className="ingest-error">{ingest.lastError}</p> : null}
    </div>
  );
}
