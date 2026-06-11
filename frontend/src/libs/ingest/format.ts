import type { IngestStatus, RuntimeBatchStatus } from "../../types";
import { formatBytes, formatInteger } from "../format";

export type IngestProgress = Record<string, string | number | boolean | null | undefined>;

export function fileListSummary(files?: string[]): string {
  if (!files?.length) {
    return "";
  }
  const visible = files.slice(0, 3).join(", ");
  const hidden = files.length - 3;
  return hidden > 0 ? `${visible}, +${formatInteger(hidden)} more` : visible;
}

export function batchSummary(batch?: RuntimeBatchStatus): string {
  if (!batch) {
    return "n/a";
  }
  const device = batch.device ? `${batch.device} ` : "";
  const mode = batch.auto ? "auto" : "manual";
  return `${device}${formatInteger(batch.active)} active | ${formatInteger(batch.recommended)} rec | ${formatInteger(batch.configured)} cfg | ${mode}`;
}

export function batchBrief(batch?: RuntimeBatchStatus): string {
  if (!batch) {
    return "n/a";
  }
  const device = batch.device ? `${batch.device.toUpperCase()} ` : "";
  return `${device}${formatInteger(batch.active)} active`;
}

export function formatDateTime(value?: string | null): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toLocaleString();
}

export function formatReason(reason?: string | null): string {
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

export function formatStage(stage?: string | null): string {
  const labels: Record<string, string> = {
    scanning: "Scanning training folder",
    processing_documents: "Processing documents",
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

export function formatDetailLabel(key: string): string {
  const labels: Record<string, string> = {
    documents: "Documents",
    rawChunks: "Raw chunks",
    chunks: "Chunks",
    droppedChunks: "Dropped chunks",
    currentDocument: "Document",
    documentPhase: "Document phase",
    fileSizeBytes: "File size",
    pdfPage: "PDF page",
    pdfPages: "PDF pages",
    extractedImages: "Extracted images",
    totalImagesToSave: "Images to save",
    savedImages: "Saved images",
    skippedImages: "Skipped image assets",
    imageCandidates: "Queued image OCR",
    skippedImageCandidates: "Tiny/invalid images",
    duplicateImageCandidates: "Duplicate image refs",
    storedImages: "Stored images",
    indexedImageTexts: "Indexed image texts",
    imageEmbeddingTexts: "Embedded image texts",
    imageEmbeddingTotal: "Image texts to embed",
    ocrImageTexts: "OCR image texts",
    ocrAccepted: "OCR accepted",
    ocrFailed: "OCR failed",
    ocrTimedOut: "OCR timed out",
    ocrSkipped: "OCR skipped",
    ocrJobs: "OCR jobs",
    currentImage: "Image",
    completedDocuments: "Indexed documents",
    failedDocuments: "Failed documents",
    failedFiles: "Failed files",
    queuedSaveDocuments: "Queued for save",
    activeWorkers: "Configured doc workers",
    activeDocumentWorkers: "Active doc workers",
    persistWorkers: "Save workers",
    queuedJobs: "Queued jobs",
    lastCompletedDocument: "Last indexed document"
  };
  return labels[key] ?? formatStage(key);
}

export function formatDetailValue(value: string | number | boolean | null | undefined): string {
  if (typeof value === "number") {
    return formatInteger(value);
  }
  if (typeof value === "boolean") {
    return value ? "yes" : "no";
  }
  return value === null || value === undefined || value === "" ? "n/a" : String(value);
}

export function activeFileRows(ingest: IngestStatus) {
  const currentFiles = ingest.currentFiles ?? [];
  const progress = ingest.fileProgress ?? {};
  return currentFiles.map((file) => ({ file, progress: progress[file] ?? {} }));
}

export function pageProgress(progress: IngestProgress): string {
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

export function fileSizeProgress(progress: IngestProgress): string {
  const value = progress.fileSizeBytes;
  if (typeof value === "number") {
    return formatBytes(value);
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? formatBytes(parsed) : value;
  }
  return "n/a";
}

export function imageProgress(progress: IngestProgress): string {
  const phase = formatDetailValue(progress.documentPhase ?? "").toLowerCase();
  const saved = numberValue(progress.savedImages);
  const totalToSave = numberValue(progress.totalImagesToSave);
  if (phase.includes("save") || totalToSave !== undefined) {
    return `${formatDetailValue(saved ?? 0)} / ${formatDetailValue(totalToSave ?? progress.extractedImages ?? progress.imageCandidates)}`;
  }

  const ocrAccepted = numberValue(progress.ocrAccepted ?? progress.ocrImageTexts);
  const ocrJobs = numberValue(progress.ocrJobs ?? progress.imageCandidates);
  if (phase.includes("ocr") && ocrJobs !== undefined) {
    const failed = numberValue(progress.ocrFailed);
    const timedOut = numberValue(progress.ocrTimedOut);
    const suffixes = [];
    if (failed) {
      suffixes.push(`${formatDetailValue(failed)} failed`);
    }
    if (timedOut) {
      suffixes.push(`${formatDetailValue(timedOut)} timed out`);
    }
    const suffix = suffixes.length ? `, ${suffixes.join(", ")}` : "";
    return `${formatDetailValue(ocrAccepted ?? 0)} / ${formatDetailValue(ocrJobs)} OCR${suffix}`;
  }

  const extracted = numberValue(progress.extractedImages);
  if (extracted !== undefined) {
    return `${formatDetailValue(extracted)} extracted`;
  }

  const candidates = numberValue(progress.imageCandidates);
  if (candidates !== undefined) {
    return `${formatDetailValue(candidates)} queued`;
  }
  return "n/a";
}

function numberValue(value: string | number | boolean | null | undefined): number | undefined {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : undefined;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

export function chunkProgress(progress: IngestProgress): string {
  const chunks = progress.chunks;
  const rawChunks = progress.rawChunks;
  const dropped = progress.droppedChunks;
  if (chunks !== undefined && rawChunks !== undefined) {
    return `${formatDetailValue(chunks)} / ${formatDetailValue(rawChunks)}`;
  }
  if (chunks !== undefined && dropped !== undefined) {
    return `${formatDetailValue(chunks)} kept`;
  }
  if (chunks !== undefined) {
    return formatDetailValue(chunks);
  }
  if (rawChunks !== undefined) {
    return formatDetailValue(rawChunks);
  }
  return "n/a";
}

export function phaseTone(progress: IngestProgress): string {
  const phase = formatDetailValue(progress.documentPhase ?? "active").toLowerCase();
  if (phase.includes("ocr")) {
    return "ocr";
  }
  if (phase.includes("save") || phase.includes("persist")) {
    return "save";
  }
  if (phase.includes("queued for db") || phase.includes("waiting for db")) {
    return "save";
  }
  if (phase.includes("embed")) {
    return "embed";
  }
  if (phase.includes("ai") || phase.includes("openai") || phase.includes("llm")) {
    return "ai";
  }
  if (phase.includes("visual") || phase.includes("render")) {
    return "visual";
  }
  if (phase.includes("waiting")) {
    return "waiting";
  }
  return "active";
}

export function compactPhase(progress: IngestProgress): string {
  const phase = progress.documentPhase;
  if (!phase) {
    return "Active";
  }
  const text = formatDetailValue(phase);
  const normalized = text.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  const labels: Record<string, string> = {
    extracting_text: "Text",
    extracting_images: "Images",
    extracting_pdf: "PDF",
    scanning_pdf_pages: "Scan PDF",
    selecting_visual_pdf_pages: "Find visuals",
    saving_rendered_pdf_pages: "Save visuals",
    ocr_image_extraction: "OCR stage",
    chunking: "Chunks",
    embedding_chunks: "Embedding",
    persisting_chunks: "Saving text",
    persisting_images: "Saving images",
    local_ai_review: "Local AI",
    openai_ingestion_review: "OpenAI",
    waiting_to_save: "Extracted",
    extracted_waiting_for_db_save: "Extracted",
    queued_for_db_save: "DB queued",
    readying_review: "Review"
  };
  return labels[text] ?? labels[normalized] ?? formatStage(text);
}
