import type { UploadDocumentsResponse } from "../types";
import { formatInteger } from "./format";

function uploadCountLabel(count: number): string {
  return `${formatInteger(count)} ${count === 1 ? "file" : "files"}`;
}

function skippedUploadSummary(response: UploadDocumentsResponse): string {
  if (!response.skippedCount) {
    return "";
  }
  const sampleNames = response.skippedFiles
    .slice(0, 3)
    .map((file) => file.filename)
    .join(", ");
  const hiddenCount = response.skippedFiles.length - Math.min(response.skippedFiles.length, 3);
  const suffix = hiddenCount > 0 ? `, +${formatInteger(hiddenCount)} more` : "";
  const reasonCounts = response.skippedFiles.reduce<Record<string, number>>((counts, file) => {
    const reason = compactSkipReason(file.reason);
    counts[reason] = (counts[reason] ?? 0) + 1;
    return counts;
  }, {});
  const reasons = Object.entries(reasonCounts)
    .slice(0, 2)
    .map(([reason, count]) => `${reason}${count > 1 ? ` (${formatInteger(count)})` : ""}`)
    .join("; ");
  return ` ${uploadCountLabel(response.skippedCount)} skipped${reasons ? `: ${reasons}` : ""}. Sample: ${sampleNames}${suffix}.`;
}

export function uploadResultMessage(response: UploadDocumentsResponse): string {
  const uploaded = response.count > 0 ? `${uploadCountLabel(response.count)} uploaded.` : "No new files uploaded.";
  const skipped = skippedUploadSummary(response);
  if (response.count <= 0) {
    return `${uploaded}${skipped}`;
  }
  if (response.indexing.started) {
    return `${uploaded}${skipped} Incremental indexing started; uploads will appear in Review before retrieval.`;
  }
  return `${uploaded}${skipped} Indexing is already running; uploaded files are queued for the next check.`;
}

function compactSkipReason(reason: string): string {
  const normalized = reason.replace(/\s+/g, " ").trim();
  if (/unsupported file type/i.test(normalized)) {
    return "Unsupported file type";
  }
  if (/already exists/i.test(normalized)) {
    return "Already exists";
  }
  if (/duplicate/i.test(normalized)) {
    return "Duplicate";
  }
  return normalized.length > 80 ? `${normalized.slice(0, 77)}...` : normalized;
}
