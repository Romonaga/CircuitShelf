import type { DatasheetIntelligence, ReviewBatchActionResponse, ReviewChunk, ReviewDocument, ReviewImage, ReviewScopeAudit } from "../../types";
import { readSessionToken, requestJson } from "./core";

export function getReviewDocuments(): Promise<{ documents: ReviewDocument[] }> {
  return requestJson<{ documents: ReviewDocument[] }>("/api/review/documents");
}

export function getReviewDocument(
  source: string,
  limit = 50
): Promise<{ document: string; displayName?: string; status?: string; chunks: ReviewChunk[]; scopeAudit?: ReviewScopeAudit[]; intelligence?: DatasheetIntelligence | null }> {
  return requestJson<{ document: string; displayName?: string; status?: string; chunks: ReviewChunk[]; scopeAudit?: ReviewScopeAudit[]; intelligence?: DatasheetIntelligence | null }>(
    `/api/review/document?source=${encodeURIComponent(source)}&limit=${encodeURIComponent(String(limit))}`
  );
}

export function getReviewDocumentImages(source: string): Promise<{ document: string; images: ReviewImage[] }> {
  return requestJson<{ document: string; images: ReviewImage[] }>(
    `/api/review/document/images?source=${encodeURIComponent(source)}`
  );
}

export async function downloadReviewDocumentSource(source: string): Promise<Blob> {
  const session = readSessionToken();
  const response = await fetch(`/api/review/document/download?source=${encodeURIComponent(source)}`, {
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

export function approveReviewDocument(source: string, includeImages = true): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>("/api/review/document/approve", {
    method: "POST",
    body: JSON.stringify({ source, includeImages })
  });
}

export function batchReviewDocuments({
  sources,
  action,
  includeImages = true,
  deleteFile = true,
  scope = "global"
}: {
  sources: string[];
  action: "approve" | "remove" | "reindex" | "scope";
  includeImages?: boolean;
  deleteFile?: boolean;
  scope?: "global" | "entity";
}): Promise<ReviewBatchActionResponse> {
  return requestJson<ReviewBatchActionResponse>("/api/review/documents/batch", {
    method: "POST",
    body: JSON.stringify({ sources, action, includeImages, deleteFile, scope })
  });
}

export function reindexReviewDocument(source: string): Promise<{ ok: boolean; queued?: boolean; source?: string; indexing?: { jobId?: number; reason?: string } }> {
  return requestJson<{ ok: boolean; queued?: boolean; source?: string; indexing?: { jobId?: number; reason?: string } }>("/api/review/document/reindex", {
    method: "POST",
    body: JSON.stringify({ source })
  });
}

export function removeReviewDocument(source: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>("/api/review/document/remove", {
    method: "POST",
    body: JSON.stringify({ source, deleteFile: true })
  });
}

export function updateReviewDocumentScope(source: string, scope: "global" | "entity", reason: string): Promise<{ ok: boolean; scopeAudit?: ReviewScopeAudit[] }> {
  return requestJson<{ ok: boolean; scopeAudit?: ReviewScopeAudit[] }>("/api/review/document/scope", {
    method: "POST",
    body: JSON.stringify({ source, scope, reason })
  });
}
