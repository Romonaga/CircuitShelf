import type { DatasheetIntelligence } from "./documents";

export interface ReviewDocument {
  source: string;
  displayName: string;
  status: string;
  entityId?: number | null;
  isGlobal?: boolean;
  entityName?: string;
  scopeLabel?: string;
  sizeBytes: number;
  fileExtension: string;
  chunkCount: number;
  imageCount: number;
  rawChunkCount?: number;
  droppedChunkCount?: number;
  extractedImageCount?: number;
  storedImageCount?: number;
  indexedImageTextCount?: number;
  ocrImageTextCount?: number;
  avgQuality: number;
  lowQualityCount: number;
  lastIngestedAt?: string | null;
  lastError?: string | null;
  updatedAt?: string | null;
}

export interface ReviewScopeAudit {
  id: number;
  source: string;
  previousIsGlobal?: boolean | null;
  previousEntityId?: number | null;
  previousEntityName?: string;
  newIsGlobal: boolean;
  newEntityId?: number | null;
  newEntityName?: string;
  changedByUserId?: number | null;
  changedByUsername?: string;
  reason: string;
  createdAt?: string | null;
}

export interface ReviewChunk {
  index: number;
  section: string;
  category: string;
  page?: number | string | null;
  tokens: number;
  quality: number;
  isOcr: boolean;
  hasMath: boolean;
  sourceImageId?: string | null;
  qualityFlags: string[];
  preview: string;
}

export interface ReviewImage {
  imageKey: string;
  caption: string;
  page?: number | string | null;
  width: number;
  height: number;
  imageMimeType?: string;
  imageBase64: string;
}

export type ReviewDocumentPayload = {
  document: string;
  displayName?: string;
  status?: string;
  chunks: ReviewChunk[];
  scopeAudit?: ReviewScopeAudit[];
  intelligence?: DatasheetIntelligence | null;
};
