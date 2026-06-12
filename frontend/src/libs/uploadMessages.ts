import type { UploadDocumentsResponse } from "../types";
import { formatInteger } from "./format";

function uploadCountLabel(count: number): string {
  return `${formatInteger(count)} ${count === 1 ? "file" : "files"}`;
}

function skippedUploadSummary(response: UploadDocumentsResponse): string {
  if (!response.skippedCount) {
    return "";
  }
  const visibleSamples = response.skippedFiles.slice(0, 3);
  const sampleNames = visibleSamples
    .map((file) => file.filename)
    .join(", ");
  const hiddenCount = Math.max(0, response.skippedCount - visibleSamples.length);
  const suffix = hiddenCount > 0 ? `, +${formatInteger(hiddenCount)} more` : "";
  const reasonCounts = response.skippedFiles.reduce<Record<string, number>>((counts, file) => {
    const reason = compactSkipReason(file.reason);
    counts[reason] = (counts[reason] ?? 0) + 1;
    return counts;
  }, {});
  const maxVisibleReasons = 3;
  const reasonEntries = Object.entries(reasonCounts).sort(([leftReason, leftCount], [rightReason, rightCount]) => {
    if (leftCount !== rightCount) {
      return rightCount - leftCount;
    }
    return leftReason.localeCompare(rightReason);
  });
  const hiddenReasonCount = Math.max(0, reasonEntries.length - maxVisibleReasons);
  const reasons = reasonEntries
    .slice(0, maxVisibleReasons)
    .map(([reason, count]) => `${reason}${count > 1 ? ` (${formatInteger(count)})` : ""}`)
    .join("; ");
  const reasonSuffix = hiddenReasonCount > 0
    ? `${reasons ? "; " : ""}+${formatInteger(hiddenReasonCount)} other ${hiddenReasonCount === 1 ? "reason" : "reasons"}`
    : "";
  const sample = sampleNames ? ` Sample: ${sampleNames}${suffix}.` : "";
  return ` ${uploadCountLabel(response.skippedCount)} skipped${reasons || reasonSuffix ? `: ${reasons}${reasonSuffix}` : ""}.${sample}`;
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
