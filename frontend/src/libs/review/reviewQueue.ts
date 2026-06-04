import type { ReviewDocument } from "../../types";

export const initialChunkPreviewLimit = 50;
export const maxChunkPreviewLimit = 500;

export function filterReviewDocuments(documents: ReviewDocument[], filter: string): ReviewDocument[] {
  const needle = filter.trim().toLowerCase();
  if (!needle) {
    return documents;
  }
  return documents.filter((doc) =>
    `${doc.displayName} ${doc.source} ${doc.status} ${doc.scopeLabel ?? ""}`.toLowerCase().includes(needle)
  );
}

export function selectNextReviewSource(documents: ReviewDocument[], currentSource: string): string {
  const nextSelected = documents.find((doc) => doc.source === currentSource) || documents[0];
  return nextSelected?.source || "";
}

export function reviewChunkPreviewCap(totalChunkCount: number): number {
  return Math.min(totalChunkCount || maxChunkPreviewLimit, maxChunkPreviewLimit);
}
