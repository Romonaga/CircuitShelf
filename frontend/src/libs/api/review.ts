import type { DatasheetIntelligence, ReviewChunk, ReviewDocument, ReviewImage, ReviewScopeAudit } from "../../types";
import { requestJson } from "./core";

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

export function approveReviewDocument(source: string, includeImages = true): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>("/api/review/document/approve", {
    method: "POST",
    body: JSON.stringify({ source, includeImages })
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
