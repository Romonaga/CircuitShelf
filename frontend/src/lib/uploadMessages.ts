import type { UploadDocumentsResponse } from "../types";
import { formatInteger } from "./format";

function uploadCountLabel(count: number): string {
  return `${formatInteger(count)} ${count === 1 ? "file" : "files"}`;
}

function skippedUploadSummary(response: UploadDocumentsResponse): string {
  if (!response.skippedCount) {
    return "";
  }
  const visibleSkipped = response.skippedFiles.slice(0, 4);
  const names = visibleSkipped.map((file) => `${file.filename} (${file.reason})`).join(", ");
  const hiddenCount = response.skippedFiles.length - visibleSkipped.length;
  const suffix = hiddenCount > 0 ? `, +${formatInteger(hiddenCount)} more` : "";
  return ` ${uploadCountLabel(response.skippedCount)} skipped: ${names}${suffix}.`;
}

export function uploadResultMessage(response: UploadDocumentsResponse): string {
  const uploaded = response.count > 0 ? `${uploadCountLabel(response.count)} uploaded.` : "No new files uploaded.";
  const skipped = skippedUploadSummary(response);
  if (response.count <= 0) {
    return `${uploaded}${skipped}`;
  }
  const indexing = response.indexing.started ? "started" : "is already running";
  return `${uploaded}${skipped} Incremental indexing ${indexing}; uploads will appear in Review before retrieval.`;
}
