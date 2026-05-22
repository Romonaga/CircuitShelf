import type { IngestStatus } from "../types";
import { formatInteger } from "../lib/format";
import { LoadingSpinner } from "./LoadingSpinner";

function fileListSummary(files?: string[]): string {
  if (!files?.length) {
    return "";
  }
  const visible = files.slice(0, 3).join(", ");
  const hidden = files.length - 3;
  return hidden > 0 ? `${visible}, +${formatInteger(hidden)} more` : visible;
}

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

function formatStage(stage?: string | null): string {
  const labels: Record<string, string> = {
    scanning: "Scanning training folder",
    processing_documents: "Extracting text and images",
    embedding_chunks: "Embedding text chunks",
    persisting_chunks: "Saving text chunks",
    persisting_images: "Saving image assets",
    readying_review: "Preparing review queue",
    failed: "Failed",
    idle: "Idle"
  };
  if (stage && labels[stage]) {
    return labels[stage];
  }
  if (!stage || stage === "idle") {
    return "Idle";
  }
  return stage
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDetailLabel(key: string): string {
  const labels: Record<string, string> = {
    documents: "Documents",
    rawChunks: "Raw chunks",
    chunks: "Chunks",
    droppedChunks: "Dropped chunks",
    extractedImages: "Extracted images",
    imageCandidates: "Indexed image OCR",
    storedImages: "Stored images",
    indexedImageTexts: "Indexed image texts",
    ocrImageTexts: "OCR image texts"
  };
  return labels[key] ?? formatStage(key);
}

function formatDetailValue(value: string | number | boolean | null | undefined): string {
  if (typeof value === "number") {
    return formatInteger(value);
  }
  if (typeof value === "boolean") {
    return value ? "yes" : "no";
  }
  return value === null || value === undefined || value === "" ? "n/a" : String(value);
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
  const totalFiles = ingest.totalFiles ?? 0;
  const processedFiles = ingest.processedFiles ?? 0;
  const currentFiles = ingest.currentFiles ?? [];
  const details = Object.entries(ingest.details ?? {}).filter(([, value]) => value !== undefined);

  return (
    <div className={hasError ? "ingest-status-panel error" : isRunning ? "ingest-status-panel running" : "ingest-status-panel"}>
      <div className="ingest-status-heading">
        <div className="ingest-status-title">
          {isRunning ? <LoadingSpinner className="ingest-spinner" /> : null}
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
        <span>Stage: {formatStage(ingest.stage)}</span>
        {isRunning && totalFiles ? <span>Progress: {formatInteger(processedFiles)} / {formatInteger(totalFiles)} files</span> : null}
        {details.map(([key, value]) => (
          <span key={key}>{formatDetailLabel(key)}: {formatDetailValue(value)}</span>
        ))}
        <span>Started: {formatDateTime(ingest.lastStartedAt)}</span>
        <span>Finished: {formatDateTime(ingest.lastFinishedAt)}</span>
        <span>Result: {ingest.lastResult || "waiting"}</span>
        <span>Next check: {formatDateTime(ingest.nextCheckAt)}</span>
      </div>
      {isRunning && currentFiles.length ? (
        <div className="ingest-current-files">
          <strong>Processing</strong>
          {currentFiles.map((file) => (
            <span key={file}>{file}</span>
          ))}
        </div>
      ) : null}
      {changes ? (
        <>
          <div className="ingest-change-list">
            <span>Added {formatInteger(changes.added)}</span>
            <span>Modified {formatInteger(changes.modified)}</span>
            <span>Removed {formatInteger(changes.removed)}</span>
            <span>Unchanged {formatInteger(changes.unchanged)}</span>
          </div>
          {changes.unchangedFiles?.length ? (
            <p className="ingest-note">Skipped unchanged: {fileListSummary(changes.unchangedFiles)}</p>
          ) : null}
        </>
      ) : null}
      {hasError ? <p className="ingest-error">{ingest.lastError}</p> : null}
    </div>
  );
}
