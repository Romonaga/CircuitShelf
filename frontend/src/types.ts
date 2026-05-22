export type RetrievalStrategy = "Vector only" | "Vector + CrossEncoder" | string;
export type View = "ask" | "bench" | "documents" | "review" | "trace" | "status" | "settings";

export interface SessionUser {
  username: string;
  isAdmin: boolean;
  token: string;
  lastActivityAt?: number;
}

export interface AppConfig {
  siteName: string;
  models: string[];
  defaultModel: string;
  authConfigured: boolean;
  retrievalStrategies: RetrievalStrategy[];
  statusPollIntervalSeconds: number;
  activeStatusPollIntervalSeconds: number;
  sessionTimeoutSeconds: number;
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
  buildCard?: CircuitBuildCard | null;
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
  rawChunkCount?: number;
  droppedChunkCount?: number;
  extractedImageCount?: number;
  storedImageCount?: number;
  indexedImageTextCount?: number;
  ocrImageTextCount?: number;
}

export interface UploadedDocument {
  filename: string;
  bytes: number;
}

export interface SkippedDocumentUpload {
  filename: string;
  reason: string;
}

export interface UploadDocumentsResponse {
  ok: boolean;
  files: UploadedDocument[];
  skippedFiles: SkippedDocumentUpload[];
  count: number;
  skippedCount: number;
  bytes: number;
  filename?: string;
  indexing: {
    started: boolean;
    status?: unknown;
  };
}

export interface RemoveDocumentResponse {
  ok: boolean;
  document?: {
    source_path?: string;
    display_name?: string;
  };
  deletedFile: boolean;
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

export interface DocumentImage {
  imageKey: string;
  caption: string;
  page?: number | string | null;
  imageMimeType?: string;
  imageBase64: string;
  ocrText?: string;
}

export interface DocumentPage {
  page: number | string;
  chunks: DocumentChunk[];
  images: DocumentImage[];
}

export interface DocumentPin {
  pin: number;
  label: string;
  function: string;
  page?: number | string | null;
  chunkIndex?: number | null;
}

export interface DocumentPinout {
  source: string;
  displayName: string;
  pins: DocumentPin[];
}

export interface DatasheetFact {
  type: string;
  label: string;
  value: string;
  unit?: string;
  page?: number | string | null;
  chunkIndex?: number | null;
  evidence?: string;
  confidence?: number;
}

export interface DatasheetIntelligence {
  source: string;
  displayName: string;
  componentName: string;
  componentType: string;
  summary: string;
  confidence: number;
  facts: DatasheetFact[];
  pinout: DocumentPinout;
  updatedAt?: string | null;
}

export interface CircuitBuildCard {
  title: string;
  componentName: string;
  componentType: string;
  summary: string;
  confidence: number;
  parts: Array<{ name: string; detail: string }>;
  power: string[];
  wiring: Array<{ from: string; to: string; note: string; page?: number | string | null }>;
  checks: string[];
  warnings: string[];
  sourceNotes: Array<{ source: string; pages: Array<number | string>; chunks: number }>;
}

export interface AssemblyPlanSummary {
  id: string;
  title: string;
  objective: string;
  componentName: string;
  componentType: string;
  confidence?: number | null;
  status: string;
  stepCount: number;
  completedStepCount: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface AssemblyPlanPart {
  id: string;
  name: string;
  detail: string;
}

export interface AssemblyPlanPowerNote {
  id: string;
  note: string;
}

export interface AssemblyPlanStep {
  id: string;
  ordinal: number;
  type: "wiring" | "check" | "warning" | string;
  title: string;
  instruction: string;
  note: string;
  sourcePath?: string | null;
  page?: number | null;
  completed: boolean;
  completedAt?: string | null;
}

export interface AssemblyPlanSource {
  id: string;
  sourcePath: string;
  displayName: string;
  pages: number[];
  chunkCount: number;
}

export interface AssemblyPlanNote {
  id: string;
  role: "user" | "assistant" | string;
  message: string;
  createdAt?: string | null;
}

export interface AssemblyPlan extends AssemblyPlanSummary {
  summary: string;
  createdBy?: string | null;
  parts: AssemblyPlanPart[];
  power: AssemblyPlanPowerNote[];
  steps: AssemblyPlanStep[];
  sources: AssemblyPlanSource[];
  notes: AssemblyPlanNote[];
}

export interface BuildAssemblyPlanResponse {
  plan?: AssemblyPlan;
  answer?: string;
  sources?: SourceSummary[];
  confidence?: number | null;
  averageQueryTime?: number | null;
  error?: string;
}

export interface DocumentDetail {
  document: string;
  displayName: string;
  chunks: DocumentChunk[];
  images: DocumentImage[];
  pages: DocumentPage[];
  pinout: DocumentPinout;
  intelligence?: DatasheetIntelligence | null;
  ingestStats?: DocumentIngestStats | null;
}

export interface DocumentIngestStats {
  rawChunkCount: number;
  chunkCount: number;
  droppedChunkCount: number;
  extractedImageCount: number;
  storedImageCount: number;
  indexedImageTextCount: number;
  ocrImageTextCount: number;
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
  ingestWorkerBudget?: IngestWorkerBudget;
  ingest?: IngestStatus;
}

export interface IngestWorkerBudget {
  cpuCores: number;
  reservedCores: number;
  usableCores: number;
  activeDocumentWorkers: number;
}

export interface LogTailPayload {
  path: string;
  exists: boolean;
  sizeBytes: number;
  lines: string[];
  truncated: boolean;
  error?: string | null;
  lineCount: number;
  updatedAt: string;
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
    unchangedFiles?: string[];
  } | null;
  nextCheckAt?: string | null;
  details?: Record<string, string | number | boolean | null | undefined>;
}

export interface ReviewDocument {
  source: string;
  displayName: string;
  status: string;
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
