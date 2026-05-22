import type { IngestStatus, IngestWorkerBudget } from "../types";
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
    currentDocument: "Document",
    documentPhase: "Document phase",
    pdfPage: "PDF page",
    pdfPages: "PDF pages",
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

function activeFileRows(ingest: IngestStatus) {
  const currentFiles = ingest.currentFiles ?? [];
  const progress = ingest.fileProgress ?? {};
  return currentFiles.map((file) => ({ file, progress: progress[file] ?? {} }));
}

function pageProgress(progress: Record<string, string | number | boolean | null | undefined>): string {
  const page = progress.pdfPage;
  const pages = progress.pdfPages;
  if (page && pages) {
    return `${formatDetailValue(page)} / ${formatDetailValue(pages)}`;
  }
  if (page) {
    return formatDetailValue(page);
  }
  return "n/a";
}

function compactPhase(progress: Record<string, string | number | boolean | null | undefined>): string {
  const phase = progress.documentPhase;
  if (!phase) {
    return "Active";
  }
  const text = formatDetailValue(phase);
  const normalized = text.toLowerCase().replace(/\s+/g, "_");
  const labels: Record<string, string> = {
    extracting_text: "Text",
    extracting_images: "Images",
    extracting_pdf: "PDF",
    scanning_pdf_pages: "Scan PDF",
    selecting_visual_pdf_pages: "Find visuals",
    saving_rendered_pdf_pages: "Save visuals",
    ocr_image_extraction: "OCR images",
    chunking: "Chunks",
    embedding_chunks: "Embedding",
    persisting_chunks: "Saving text",
    persisting_images: "Saving images",
    readying_review: "Review"
  };
  return labels[text] ?? labels[normalized] ?? formatStage(text);
}

export function IngestStatusPanel({
  ingest,
  workerBudget,
  pendingReview,
  onOpenReview
}: {
  ingest?: IngestStatus | null;
  workerBudget?: IngestWorkerBudget | null;
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
  const fileRows = activeFileRows(ingest);
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
      {workerBudget ? (
        <div className="ingest-worker-budget">
          <span>Cores {formatInteger(workerBudget.cpuCores)}</span>
          <span>Reserved {formatInteger(workerBudget.reservedCores)}</span>
          <span>Usable {formatInteger(workerBudget.usableCores)}</span>
          <span>Active workers {formatInteger(workerBudget.activeDocumentWorkers)}</span>
        </div>
      ) : null}
      {isRunning && fileRows.length ? (
        <div className="ingest-file-grid">
          <div className="ingest-file-grid-heading">
            <span>File</span>
            <span>Phase</span>
            <span>Page</span>
            <span>Images</span>
          </div>
          {fileRows.map(({ file, progress }) => (
            <div key={file} className="ingest-file-row">
              <strong title={file}>{file}</strong>
              <span title={formatDetailValue(progress.documentPhase ?? "Active")}>{compactPhase(progress)}</span>
              <span>{pageProgress(progress)}</span>
              <span>{formatDetailValue(progress.imageCandidates)}</span>
            </div>
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
