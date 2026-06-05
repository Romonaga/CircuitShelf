import type { DocumentDetail, DocumentSummary, RemoveDocumentResponse, UploadDocumentsResponse } from "../../types";
import { readSessionToken, requestJson } from "./core";

export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
  computable: boolean;
  bytesPerSecond?: number | null;
  etaSeconds?: number | null;
  elapsedSeconds?: number | null;
  activeUploads?: number;
  completedBatches?: number;
  totalBatches?: number;
}

const CONCURRENT_UPLOADS = 4;

export function getDocuments(scope = "visible"): Promise<{ documents: DocumentSummary[] }> {
  return requestJson<{ documents: DocumentSummary[] }>(`/api/documents?scope=${encodeURIComponent(scope)}`);
}

export function uploadDocuments(
  files: File[],
  overwrite: boolean,
  scope = "entity",
  onProgress?: (progress: UploadProgress) => void
): Promise<UploadDocumentsResponse> {
  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
  const batches = splitUploadBatches(files);
  if (batches.length > 1) {
    return uploadDocumentBatches(batches, overwrite, scope, totalBytes, CONCURRENT_UPLOADS, onProgress);
  }
  return uploadDocumentBatch(files, overwrite, scope, false, totalBytes, 0, performance.now(), onProgress);
}

function splitUploadBatches(files: File[]): File[][] {
  const maxFiles = 6;
  const maxBytes = 96 * 1024 * 1024;
  const batches: File[][] = [];
  let current: File[] = [];
  let currentBytes = 0;
  for (const file of files) {
    const wouldOverflow = current.length > 0 && (current.length >= maxFiles || currentBytes + file.size > maxBytes);
    if (wouldOverflow) {
      batches.push(current);
      current = [];
      currentBytes = 0;
    }
    current.push(file);
    currentBytes += file.size;
  }
  if (current.length) {
    batches.push(current);
  }
  return batches;
}

async function uploadDocumentBatches(
  batches: File[][],
  overwrite: boolean,
  scope: string,
  totalBytes: number,
  concurrency: number,
  onProgress?: (progress: UploadProgress) => void
): Promise<UploadDocumentsResponse> {
  const startedAt = performance.now();
  const aggregate: UploadDocumentsResponse = {
    ok: true,
    files: [],
    skippedFiles: [],
    count: 0,
    skippedCount: 0,
    bytes: 0,
    indexing: { started: false }
  };
  const batchTotals = batches.map((batch) => batch.reduce((sum, file) => sum + file.size, 0));
  const batchLoaded = new Array<number>(batches.length).fill(0);
  const batchDone = new Array<boolean>(batches.length).fill(false);
  let activeUploads = 0;
  let nextBatchIndex = 0;
  let completedBatches = 0;

  const emitProgress = () => {
    const loaded = Math.min(totalBytes, batchLoaded.reduce((sum, value) => sum + value, 0));
    const elapsedSeconds = Math.max((performance.now() - startedAt) / 1000, 0);
    const bytesPerSecond = elapsedSeconds > 0.2 ? loaded / elapsedSeconds : null;
    const etaSeconds = bytesPerSecond && totalBytes > loaded ? (totalBytes - loaded) / bytesPerSecond : null;
    onProgress?.({
      loaded,
      total: totalBytes,
      percent: totalBytes > 0 ? Math.min(100, Math.round((loaded / totalBytes) * 100)) : 0,
      computable: true,
      bytesPerSecond,
      etaSeconds,
      elapsedSeconds,
      activeUploads,
      completedBatches,
      totalBatches: batches.length
    });
  };

  const workerCount = Math.max(1, Math.min(concurrency, batches.length));
  async function runWorker() {
    while (nextBatchIndex < batches.length) {
      const index = nextBatchIndex;
      nextBatchIndex += 1;
      activeUploads += 1;
      emitProgress();
      try {
        const result = await uploadDocumentBatch(
          batches[index],
          overwrite,
          scope,
          true,
          batchTotals[index],
          0,
          startedAt,
          (progress) => {
            batchLoaded[index] = Math.min(batchTotals[index], progress.loaded);
            emitProgress();
          }
        );
        aggregate.files.push(...(result.files ?? []));
        aggregate.skippedFiles.push(...(result.skippedFiles ?? []));
        aggregate.count += result.count ?? 0;
        aggregate.skippedCount += result.skippedCount ?? 0;
        aggregate.bytes += result.bytes ?? 0;
      } catch (error) {
        const reason = error instanceof Error ? error.message : "Upload failed";
        for (const file of batches[index]) {
          aggregate.skippedFiles.push({ filename: file.webkitRelativePath || file.name, reason });
          aggregate.skippedCount += 1;
        }
      } finally {
        batchLoaded[index] = batchTotals[index];
        batchDone[index] = true;
        completedBatches = batchDone.filter(Boolean).length;
        activeUploads = Math.max(0, activeUploads - 1);
        emitProgress();
      }
    }
  }

  await Promise.all(Array.from({ length: workerCount }, () => runWorker()));

  if (aggregate.count > 0) {
    aggregate.indexing = await triggerIndexCheck();
  }
  return aggregate;
}

function uploadDocumentBatch(
  files: File[],
  overwrite: boolean,
  scope: string,
  deferIndex: boolean,
  totalBytes: number,
  completedBytes: number,
  startedAt: number,
  onProgress?: (progress: UploadProgress) => void
): Promise<UploadDocumentsResponse> {
  const body = new FormData();
  files.forEach((file) => body.append("files", file, file.webkitRelativePath || file.name));
  const session = readSessionToken();
  const path = `/api/documents/upload-batch?overwrite=${overwrite ? "true" : "false"}&scope=${encodeURIComponent(scope)}&defer_index=${deferIndex ? "true" : "false"}`;

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path);
    if (session) {
      xhr.setRequestHeader("Authorization", `Bearer ${session}`);
    }

    xhr.upload.onprogress = (event) => {
      const total = totalBytes || (event.lengthComputable ? event.total : files.reduce((sum, file) => sum + file.size, 0));
      const loaded = Math.min(total, completedBytes + event.loaded);
      const elapsedSeconds = Math.max((performance.now() - startedAt) / 1000, 0);
      const bytesPerSecond = elapsedSeconds > 0.2 ? loaded / elapsedSeconds : null;
      const etaSeconds = bytesPerSecond && total > loaded ? (total - loaded) / bytesPerSecond : null;
      onProgress?.({
        loaded,
        total,
        percent: total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0,
        computable: event.lengthComputable,
        bytesPerSecond,
        etaSeconds,
        elapsedSeconds
      });
    };

    xhr.onload = () => {
      let data: UploadDocumentsResponse & { error?: string };
      try {
        data = xhr.responseText
          ? (JSON.parse(xhr.responseText) as UploadDocumentsResponse & { error?: string })
          : ({} as UploadDocumentsResponse & { error?: string });
      } catch {
        reject(new Error(`Expected JSON from ${path}, got ${xhr.status}: ${xhr.responseText.slice(0, 160)}`));
        return;
      }

      if (xhr.status === 401) {
        window.dispatchEvent(new Event("circuitshelf-auth-expired"));
      }
      if (xhr.status < 200 || xhr.status >= 300 || data.error) {
        reject(new Error(data.error || `Upload failed with status ${xhr.status}`));
        return;
      }
      resolve(data);
    };

    xhr.onerror = () => reject(new Error("Upload failed due to a network error."));
    xhr.onabort = () => reject(new Error("Upload was cancelled."));
    xhr.send(body);
  });
}

export function removeIndexedDocument(source: string): Promise<RemoveDocumentResponse> {
  return requestJson<RemoveDocumentResponse>("/api/document/remove", {
    method: "POST",
    body: JSON.stringify({ source, deleteFile: true })
  });
}

export function triggerIndexCheck(): Promise<{ ok: boolean; started: boolean; status: unknown }> {
  return requestJson<{ ok: boolean; started: boolean; status: unknown }>("/api/index/check", { method: "POST" });
}

export function getDocument(source: string, scope = "visible"): Promise<DocumentDetail> {
  return requestJson<DocumentDetail>(`/api/document?source=${encodeURIComponent(source)}&scope=${encodeURIComponent(scope)}`);
}

export async function downloadDocumentSource(source: string, scope = "visible"): Promise<Blob> {
  const session = readSessionToken();
  const response = await fetch(`/api/document/download?source=${encodeURIComponent(source)}&scope=${encodeURIComponent(scope)}`, {
    headers: {
      ...(session ? { Authorization: `Bearer ${session}` } : {})
    }
  });
  if (response.status === 401) {
    window.dispatchEvent(new Event("circuitshelf-auth-expired"));
  }
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Download failed with status ${response.status}`);
  }
  return response.blob();
}
