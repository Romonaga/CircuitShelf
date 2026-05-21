export type RetrievalStrategy = "Vector only" | "Vector + CrossEncoder" | string;
export type View = "ask" | "documents" | "review" | "trace" | "status" | "settings";

export interface SessionUser {
  username: string;
  isAdmin: boolean;
  token: string;
}

export interface AppConfig {
  siteName: string;
  models: string[];
  defaultModel: string;
  authConfigured: boolean;
  retrievalStrategies: RetrievalStrategy[];
  statusPollIntervalSeconds: number;
  activeStatusPollIntervalSeconds: number;
  defaults: QueryOptions;
}

export interface QueryOptions {
  topK: number;
  distanceThreshold: number;
  maxTokens: number;
  showFullText: boolean;
  bypassCache: boolean;
  strategy: RetrievalStrategy;
}

export interface QueryRequest extends QueryOptions {
  question: string;
  model: string;
  chatHistory: ChatTurn[];
}

export type ChatTurn = [string, string];

export interface QueryResponse {
  question: string;
  answer: string;
  chatHistory: ChatTurn[];
  sources: SourceSummary[];
  cacheStats: unknown;
  confidence: number | null;
  averageQueryTime: number | null;
  error?: string;
}

export interface DocumentSummary {
  source: string;
  displayName?: string;
  chunkCount: number;
  imageCount: number;
}

export interface UploadedDocument {
  filename: string;
  bytes: number;
}

export interface UploadDocumentsResponse {
  ok: boolean;
  files: UploadedDocument[];
  count: number;
  bytes: number;
  filename?: string;
  indexing: {
    started: boolean;
    status?: unknown;
  };
}

export interface SourceChunk {
  index?: number | null;
  page?: number | string | null;
  section?: string;
  category?: string;
  distance?: number | null;
  sourceImageId?: string | null;
  preview?: string;
}

export interface SourceSummary {
  source: string;
  displayName?: string;
  pages?: Array<number | string>;
  chunkCount?: number;
  chunks?: SourceChunk[];
}

export interface DocumentChunk {
  index: number;
  section: string;
  category: string;
  page?: number | string | null;
  sourceImageId?: string | null;
  tokens: number;
  preview: string;
}

export interface StatusPayload {
  chunks: number;
  sources: number;
  embeddings: number;
  vectorChunks?: number;
  vectorEmbeddings?: number;
  imageIds: number;
  imageEmbeddings: number;
  pendingReview?: number;
  cacheStats: unknown;
  ingest?: IngestStatus;
}

export type SettingValueType = "text" | "integer" | "numeric" | "boolean";
export type SettingValue = string | number | boolean;

export interface AppSetting {
  key: string;
  label: string;
  group: string;
  groupLabel: string;
  groupDescription?: string;
  value: SettingValue;
  valueType: SettingValueType;
  description: string;
  rawDescription?: string;
  advanced: boolean;
  updatedAt?: string | null;
  restartRequired: boolean;
}

export interface IngestStatus {
  enabled: boolean;
  running: boolean;
  stage?: string | null;
  currentFiles?: string[];
  processedFiles?: number;
  totalFiles?: number;
  lastStartedAt?: string | null;
  lastFinishedAt?: string | null;
  lastReason?: string | null;
  lastResult?: string | null;
  lastError?: string | null;
  lastChanges?: {
    added: number;
    modified: number;
    removed: number;
    unchanged: number;
    addedFiles?: string[];
    modifiedFiles?: string[];
    removedFiles?: string[];
  } | null;
  nextCheckAt?: string | null;
}

export interface ReviewDocument {
  source: string;
  displayName: string;
  status: string;
  sizeBytes: number;
  fileExtension: string;
  chunkCount: number;
  imageCount: number;
  avgQuality: number;
  lowQualityCount: number;
  lastIngestedAt?: string | null;
  lastError?: string | null;
  updatedAt?: string | null;
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
