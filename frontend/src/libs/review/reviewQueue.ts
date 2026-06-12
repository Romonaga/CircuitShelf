import type { ReviewDocument } from "../../types";

export const initialChunkPreviewLimit = 50;
export const maxChunkPreviewLimit = 500;

export type ReviewDocumentKindFilter = "all" | "pdf" | "code" | "text" | "metadata" | "other";
export type ReviewHealthFilter =
  | "all"
  | "ready"
  | "failed"
  | "no-chunks"
  | "low-quality"
  | "with-images"
  | "without-images";

export interface ReviewTriageFilters {
  search: string;
  kind: ReviewDocumentKindFilter;
  health: ReviewHealthFilter;
  folder: string;
}

export const defaultReviewTriageFilters: ReviewTriageFilters = {
  search: "",
  kind: "all",
  health: "all",
  folder: "all"
};

const codeExtensions = new Set([
  ".bash",
  ".c",
  ".cc",
  ".cpp",
  ".go",
  ".h",
  ".hh",
  ".hpp",
  ".ino",
  ".java",
  ".js",
  ".jsx",
  ".lua",
  ".m",
  ".mm",
  ".php",
  ".py",
  ".rb",
  ".rs",
  ".sh",
  ".ts",
  ".tsx"
]);
const textExtensions = new Set([".csv", ".log", ".md", ".rst", ".text", ".txt"]);
const metadataExtensions = new Set([".json", ".toml", ".xml", ".yaml", ".yml"]);

export function filterReviewDocuments(
  documents: ReviewDocument[],
  filters: ReviewTriageFilters
): ReviewDocument[] {
  const needle = filters.search.trim().toLowerCase();
  return documents.filter((doc) => {
    if (needle) {
      const haystack = `${doc.displayName} ${doc.source} ${doc.status} ${doc.scopeLabel ?? ""}`.toLowerCase();
      if (!haystack.includes(needle)) {
        return false;
      }
    }
    if (filters.kind !== "all" && reviewDocumentKind(doc) !== filters.kind) {
      return false;
    }
    if (filters.health !== "all" && !matchesHealthFilter(doc, filters.health)) {
      return false;
    }
    if (filters.folder !== "all" && reviewDocumentFolder(doc) !== filters.folder) {
      return false;
    }
    return true;
  });
}

export function selectNextReviewSource(documents: ReviewDocument[], currentSource: string): string {
  const nextSelected = documents.find((doc) => doc.source === currentSource) || documents[0];
  return nextSelected?.source || "";
}

export function reviewChunkPreviewCap(totalChunkCount: number): number {
  return Math.min(totalChunkCount || maxChunkPreviewLimit, maxChunkPreviewLimit);
}

export function reviewDocumentFolder(document: ReviewDocument): string {
  const source = document.source.trim();
  if (!source.includes("/")) {
    return "(root)";
  }
  const firstSegment = source.split("/").find(Boolean);
  return firstSegment || "(root)";
}

export function reviewFolderOptions(documents: ReviewDocument[]): string[] {
  return [...new Set(documents.map((doc) => reviewDocumentFolder(doc)))].sort((a, b) => a.localeCompare(b));
}

export function reviewDocumentKind(document: ReviewDocument): ReviewDocumentKindFilter {
  const extension = normalizeExtension(document.fileExtension || document.source);
  if (extension === ".pdf") {
    return "pdf";
  }
  if (codeExtensions.has(extension)) {
    return "code";
  }
  if (textExtensions.has(extension)) {
    return "text";
  }
  if (metadataExtensions.has(extension)) {
    return "metadata";
  }
  return "other";
}

export function reviewDocumentKindLabel(document: ReviewDocument): string {
  const kind = reviewDocumentKind(document);
  if (kind === "pdf") {
    return "PDF";
  }
  if (kind === "code") {
    return "Code";
  }
  if (kind === "metadata") {
    return "Metadata";
  }
  if (kind === "text") {
    return "Text";
  }
  return "Other";
}

export function reviewDocumentHasImages(document: ReviewDocument): boolean {
  return (
    document.imageCount > 0
    || Number(document.extractedImageCount || 0) > 0
    || Number(document.storedImageCount || 0) > 0
  );
}

export function reviewDocumentFailed(document: ReviewDocument): boolean {
  const status = document.status.toLowerCase();
  return Boolean(document.lastError) || status.includes("fail") || status.includes("error");
}

export function reviewDocumentLowQuality(document: ReviewDocument): boolean {
  return document.lowQualityCount > 0 || (document.chunkCount > 0 && document.avgQuality < 0.35);
}

function matchesHealthFilter(document: ReviewDocument, filter: ReviewHealthFilter): boolean {
  if (filter === "failed") {
    return reviewDocumentFailed(document);
  }
  if (filter === "no-chunks") {
    return document.chunkCount <= 0;
  }
  if (filter === "low-quality") {
    return reviewDocumentLowQuality(document);
  }
  if (filter === "with-images") {
    return reviewDocumentHasImages(document);
  }
  if (filter === "without-images") {
    return !reviewDocumentHasImages(document);
  }
  return !reviewDocumentFailed(document) && document.chunkCount > 0;
}

function normalizeExtension(value: string): string {
  const trimmed = value.trim().toLowerCase();
  if (!trimmed) {
    return "";
  }
  if (trimmed.startsWith(".")) {
    return trimmed;
  }
  const match = trimmed.match(/\.[a-z0-9]+$/);
  return match?.[0] || "";
}
