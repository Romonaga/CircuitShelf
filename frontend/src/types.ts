export type RetrievalStrategy = "Vector only" | "Vector + CrossEncoder" | string;
export type View = "ask" | "bench" | "finder" | "inventory" | "documents" | "corpus" | "review" | "trace" | "status" | "performance" | "aiUsage" | "settings" | "runtime" | "entity" | "account";

export interface EntityContext {
  id: number;
  name: string;
  slug: string;
  role: string;
  roleName: string;
  canManage: boolean;
  ownerUserId?: number | null;
}

export interface SessionUser {
  userId?: number;
  username: string;
  isAdmin: boolean;
  canManageSystem?: boolean;
  forcePasswordChange?: boolean;
  entity?: EntityContext | null;
  token: string;
  lastActivityAt?: number;
}

export interface AccountProfile {
  userId: number;
  username: string;
  email: string;
  displayName: string;
  nickname: string;
  phone: string;
  address: string;
  isAdmin: boolean;
  canManageSystem: boolean;
  forcePasswordChange: boolean;
  passwordChangedAt?: string | null;
  lastLoginAt?: string | null;
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

export interface EntityMember {
  userId: number;
  username: string;
  email?: string | null;
  displayName?: string | null;
  nickname?: string | null;
  isActive: boolean;
  canManageSystem: boolean;
  forcePasswordChange?: boolean;
  failedLoginCount?: number;
  disabledAt?: string | null;
  disabledReason?: string | null;
  role: string;
  roleName: string;
  canManage: boolean;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface PasswordPolicy {
  id?: number;
  entityId?: number | null;
  minLength: number;
  requireUpper: boolean;
  requireLower: boolean;
  requireNumber: boolean;
  requireSymbol: boolean;
  passwordChangeDays: number;
  maxFailedAttempts: number;
  lockoutMinutes: number;
  updatedAt?: string | null;
}

export interface AIModelPricing {
  provider: string;
  modelName: string;
  inputPerMillion: number;
  cachedInputPerMillion: number;
  outputPerMillion: number;
  currency: string;
  isActive: boolean;
  updatedAt?: string | null;
}

export interface AIAvailableModel {
  id: string;
  ownedBy: string;
  created: number;
}

export interface AIModelPricingOverride {
  provider?: string;
  modelName: string;
  scope?: string;
  entityId?: number | null;
  userId?: number | null;
  inputPerMillion: number;
  cachedInputPerMillion: number;
  outputPerMillion: number;
  currency?: string;
  updatedAt?: string | null;
}

export interface AIProviderSettings {
  scope: "system" | "entity" | "user" | string;
  provider: string;
  enabled: boolean;
  hasApiKey: boolean;
  keyPreview: string;
  keyPolicy: string;
  assistMode: string;
  defaultModel: string;
  monthlyBudget: number;
  warnPercent: number;
  stopPercent: number;
  pricingOverrides: AIModelPricingOverride[];
  updatedAt?: string | null;
}

export interface AIProviderSettingsPayload {
  enabled: boolean;
  apiKey?: string;
  clearApiKey?: boolean;
  keyPolicy?: string;
  assistMode: string;
  defaultModel: string;
  monthlyBudget: number;
  warnPercent: number;
  stopPercent: number;
  pricingOverrides?: AIModelPricingOverride[];
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
  conversationId?: string | null;
}

export type ChatTurn = [string, string];

export interface ConversationTurn {
  id: string;
  ordinal: number;
  question: string;
  answer: string;
  modelName?: string | null;
  retrievalStrategy?: string | null;
  confidence?: number | null;
  createdAt?: string | null;
}

export interface ConversationSummary {
  id: string;
  userId?: number | null;
  username?: string | null;
  title: string;
  turnCount: number;
  createdAt?: string | null;
  updatedAt?: string | null;
  lastTurnAt?: string | null;
}

export interface ConversationDetail extends ConversationSummary {
  turns: ConversationTurn[];
}

export interface QueryResponse {
  conversation?: ConversationDetail | null;
  question: string;
  answer: string;
  chatHistory: ChatTurn[];
  sources: SourceSummary[];
  buildCard?: CircuitBuildCard | null;
  validation?: ResponseValidation | null;
  cacheStats: unknown;
  confidence: number | null;
  averageQueryTime: number | null;
  error?: string;
}

export interface ResponseValidation {
  enabled: boolean;
  ran: boolean;
  useful: boolean;
  changed: boolean;
  confidence?: number | null;
  issues: string[];
  notes: string[];
  elapsedMs: number;
  model?: string | null;
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
  userId?: number | null;
  createdBy?: string | null;
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

export interface AssemblyStepEvidenceChunk {
  sourcePath: string;
  displayName: string;
  chunkIndex: number;
  page?: number | null;
  section: string;
  category: string;
  quality?: number | null;
  preview: string;
}

export interface AssemblyStepEvidenceImage {
  sourcePath: string;
  displayName: string;
  imageKey: string;
  caption: string;
  page?: number | null;
  width: number;
  height: number;
  imageMimeType: string;
  imageBase64: string;
}

export interface AssemblyStepEvidence {
  chunks: AssemblyStepEvidenceChunk[];
  images: AssemblyStepEvidenceImage[];
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
  parts: AssemblyPlanPart[];
  power: AssemblyPlanPowerNote[];
  steps: AssemblyPlanStep[];
  sources: AssemblyPlanSource[];
  notes: AssemblyPlanNote[];
}

export interface AssemblyPlanExport {
  filename: string;
  mimeType: string;
  content: string;
}

export interface AssemblyLearningSession {
  planId: string;
  currentOrdinal: number;
  modeEnabled: boolean;
  stepCount: number;
  currentStep?: AssemblyPlanStep | null;
  prompt: string;
}

export interface AssemblyPhotoCheck {
  id: string;
  planId: string;
  userId: number;
  imageMimeType: string;
  note: string;
  checklist: string;
  diagnostics?: BenchPhotoDiagnostics;
  createdAt?: string | null;
}

export interface BenchPhotoDiagnostics {
  width?: number;
  height?: number;
  brightness?: number;
  contrast?: number;
  edgeDensity?: number;
  blurScore?: number;
  dominantColors?: Array<{ hex: string; percent: number }>;
  wireColorPixels?: Record<string, number>;
  warnings?: string[];
}

export interface BuildAssemblyPlanResponse {
  plan?: AssemblyPlan;
  answer?: string;
  sources?: SourceSummary[];
  validation?: ResponseValidation | null;
  confidence?: number | null;
  averageQueryTime?: number | null;
  error?: string;
}

export interface InventoryPart {
  id: string;
  userId?: number;
  displayName: string;
  normalizedName?: string;
  partType: string;
  quantity: number;
  location: string;
  notes: string;
  aliases: string[];
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface InventoryPartInput {
  id?: string;
  displayName: string;
  partType: string;
  quantity: number;
  location: string;
  notes: string;
  aliases: string[];
}

export interface InventoryImportItem extends InventoryPartInput {
  rawLine: string;
  normalizedName?: string;
  confidence: number;
  warnings: string[];
  action?: "create" | "merge" | string;
  existingPartId?: string | null;
  selected?: boolean;
}

export interface InventoryImportPreview {
  items: InventoryImportItem[];
  count: number;
}

export interface ProjectCandidatePart {
  id?: string;
  displayName?: string;
  name?: string;
  partType?: string;
  type?: string;
  quantity?: number;
  location?: string;
}

export interface ProjectCandidate {
  id: string;
  kind: "project_chunk" | "component_reference" | string;
  title: string;
  objective: string;
  summary: string;
  source: string;
  displayName: string;
  page?: number | null;
  chunkIndex?: number | null;
  matchedParts: ProjectCandidatePart[];
  matchedPartCount: number;
  requiredParts: ProjectCandidatePart[];
  missingParts: ProjectCandidatePart[];
  suggestedSubstitutions: Array<Record<string, string>>;
  buildable: boolean;
  score: number;
}

export interface ProjectMissingPartSummary {
  name: string;
  type: string;
  count: number;
  exampleTitles: string[];
}

export interface ProjectFinderResponse {
  inventoryCount: number;
  termCount?: number;
  buildableCount?: number;
  needsPartsCount?: number;
  missingPartSummary?: ProjectMissingPartSummary[];
  candidates: ProjectCandidate[];
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
  runtimeBatches?: RuntimeBatches;
  systemResources?: SystemResources;
  ingest?: IngestStatus;
}

export interface IngestWorkerBudget {
  cpuCores: number;
  reservedCores: number;
  usableCores: number;
  activeDocumentWorkers: number;
}

export interface RuntimeBatchStatus {
  model?: string | null;
  configured: number;
  recommended: number;
  active: number;
  auto: boolean;
}

export interface RuntimeBatches {
  embedding: RuntimeBatchStatus;
  reranker: RuntimeBatchStatus;
}

export interface SystemResources {
  sampledAt?: string;
  cpu?: {
    cores?: number;
    utilizationPercent?: number | null;
    loadAverage?: number[] | null;
  };
  memory?: {
    totalBytes?: number;
    usedBytes?: number;
    availableBytes?: number;
    usedPercent?: number | null;
  };
  process?: {
    pid?: number;
    memoryBytes?: number;
    cpuPercent?: number | null;
    threads?: number;
  };
  gpu?: {
    available?: boolean;
    name?: string;
    utilizationPercent?: number | null;
    memoryUsedMiB?: number;
    memoryTotalMiB?: number;
    memoryUsedPercent?: number | null;
    temperatureC?: number | null;
    powerW?: number | null;
    error?: string | null;
  };
}

export interface PerformanceSample {
  sampledAt?: string | null;
  cpu?: number | null;
  processCpu?: number | null;
  processMemoryBytes?: number | null;
  processThreads?: number | null;
  ram?: number | null;
  gpu?: number | null;
  vram?: number | null;
  gpuMemoryUsedMiB?: number | null;
  gpuMemoryTotalMiB?: number | null;
  gpuTemperatureC?: number | null;
  gpuPowerW?: number | null;
  workers: number;
  embeddingBatch: number;
  rerankerBatch: number;
  chunks: number;
  sources: number;
  images: number;
}

export interface PerformanceWorkRun {
  id: number;
  workType: string;
  workTypeLabel: string;
  entityId?: number | null;
  entityName?: string | null;
  userId?: number | null;
  username?: string | null;
  label: string;
  triggerReason: string;
  status: string;
  sourcePath: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  durationMs: number;
  chunks: number;
  images: number;
  droppedChunks: number;
  details: Record<string, unknown>;
  errorMessage?: string | null;
}

export interface PerformanceReport {
  available: boolean;
  samples: PerformanceSample[];
  recentWork: PerformanceWorkRun[];
  error?: string;
}

export interface AIUsageBreakdown {
  label: string;
  calls: number;
  tokens: number;
  estimatedCost: number;
}

export interface AIUsageEvent {
  id: number;
  createdAt?: string | null;
  entityId?: number | null;
  entityName?: string | null;
  userId?: number | null;
  username: string;
  provider: string;
  taskType: string;
  taskLabel: string;
  modelName: string;
  contextType: string;
  contextId: string;
  roundNumber: number;
  roundCount: number;
  inputTokens: number;
  cachedInputTokens: number;
  outputTokens: number;
  estimatedCost: number;
  paidBy: string;
  providerKeyOwnerUserId?: number | null;
  providerKeyOwnerUsername?: string | null;
  success: boolean;
  errorMessage?: string | null;
}

export interface AIUsageReport {
  summary: {
    calls: number;
    successfulCalls: number;
    tokens: number;
    inputTokens: number;
    cachedInputTokens: number;
    outputTokens: number;
    estimatedCost: number;
  };
  byTask: AIUsageBreakdown[];
  byUser: AIUsageBreakdown[];
  byPayer: AIUsageBreakdown[];
  byModel: AIUsageBreakdown[];
  byContext: AIUsageBreakdown[];
  events: AIUsageEvent[];
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

export interface RuntimeLlmModel {
  id: number;
  modelName: string;
  displayName: string;
  provider: string;
  isDefault: boolean;
  isEnabled: boolean;
  temperature: number;
  numPredict: number;
  numCtx?: number | null;
  updatedAt?: string | null;
}

export interface RuntimeRerankProfile {
  id: number;
  name: string;
  weightVector: number;
  weightRerank: number;
  isDefault: boolean;
  keywords: string[];
  updatedAt?: string | null;
}

export interface RuntimeEquationPattern {
  id: number;
  patternType: string;
  pattern: string;
  isRegex: boolean;
  createdAt?: string | null;
}

export interface RuntimeCatalog {
  llmModels: RuntimeLlmModel[];
  rerankProfiles: RuntimeRerankProfile[];
  equationPatterns: RuntimeEquationPattern[];
}

export interface IngestStatus {
  enabled: boolean;
  running: boolean;
  stage?: string | null;
  currentFiles?: string[];
  fileProgress?: Record<string, Record<string, string | number | boolean | null | undefined>>;
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
