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
  databasePool?: DatabasePoolStatus;
  ingestWorkerBudget?: IngestWorkerBudget;
  runtimeBatches?: RuntimeBatches;
  localGpuQueue?: LocalGpuQueueStatus;
  localLlmQueue?: LocalLlmQueueStatus;
  systemResources?: SystemResources;
  ingest?: IngestStatus;
}

export interface DatabasePoolStatus {
  enabled: boolean;
  open: boolean;
  minSize: number;
  maxSize: number;
  [key: string]: string | number | boolean | null | undefined;
}

export interface IngestWorkerBudget {
  cpuCores: number;
  reservedCores: number;
  usableCores: number;
  activeDocumentWorkers: number;
  documentWorkerCapacity?: number;
}

export interface RuntimeBatchStatus {
  model?: string | null;
  device?: string | null;
  configured: number;
  recommended: number;
  active: number;
  auto: boolean;
}

export interface RuntimeBatches {
  embedding: RuntimeBatchStatus;
  reranker: RuntimeBatchStatus;
}

export interface LocalLlmQueueStatus {
  enabled: boolean;
  maxConcurrent?: number;
  queueTimeoutSeconds?: number;
  active?: number;
  waiting?: number;
  completed?: number;
  timedOut?: number;
  lastWaitSeconds?: number;
  keepAlive?: string | number | null;
  error?: string | null;
}

export interface LocalGpuQueueItem {
  taskId: string;
  resourceClass?: string | null;
  taskType: string;
  priority: number;
  owner?: string | null;
  processId?: number | null;
  slotIndex?: number | null;
  status: string;
  waitSeconds?: number | null;
  durationSeconds?: number | null;
  error?: string | null;
  details?: Record<string, unknown>;
  createdAt?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  updatedAt?: string | null;
}

export interface LocalGpuQueueStatus {
  enabled: boolean;
  slots?: number;
  llmSlots?: number;
  cudaSlots?: number;
  ocrSlots?: number;
  detectedGpus?: number;
  processId?: number;
  queueTimeoutSeconds?: number;
  active?: number;
  queued?: number;
  completed?: number;
  failed?: number;
  timedOut?: number;
  wait?: {
    queued?: number;
    running?: number;
    currentAvgWaitSeconds?: number | null;
    currentMaxWaitSeconds?: number | null;
    recentAvgWaitSeconds?: number | null;
    recentMaxWaitSeconds?: number | null;
  };
  byResource?: Record<string, Record<string, number | null | undefined>>;
  recent?: LocalGpuQueueItem[];
  error?: string | null;
}

export interface SystemResources {
  sampledAt?: string;
  cpu?: {
    cores?: number;
    utilizationPercent?: number | null;
    temperatureC?: number | null;
    temperatureSensor?: string | null;
    powerW?: number | null;
    powerSensor?: string | null;
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
  peaks?: {
    windowDate?: string | null;
    windowStartedAt?: string | null;
    cpuPercent?: number | null;
    cpuTemperatureC?: number | null;
    cpuPowerW?: number | null;
    processCpuPercent?: number | null;
    memoryUsedPercent?: number | null;
    processMemoryBytes?: number | null;
    processThreads?: number | null;
    gpuPercent?: number | null;
    gpuMemoryUsedPercent?: number | null;
    gpuMemoryUsedMiB?: number | null;
    gpuTemperatureC?: number | null;
    gpuPowerW?: number | null;
    activeDocumentWorkers?: number | null;
  };
}

export interface PerformanceSample {
  sampledAt?: string | null;
  cpu?: number | null;
  cpuTemperatureC?: number | null;
  cpuPowerW?: number | null;
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
  workerCapacity?: number | null;
  embeddingBatch: number;
  rerankerBatch: number;
  chunks: number;
  sources: number;
  images: number;
  gpuQueueActive?: number;
  gpuQueueQueued?: number;
  gpuQueueCudaQueued?: number;
  gpuQueueOcrQueued?: number;
  gpuQueueLlmQueued?: number;
  gpuQueueCurrentWaitSeconds?: number | null;
  gpuQueueRecentAvgWaitSeconds?: number | null;
  gpuQueueRecentMaxWaitSeconds?: number | null;
}

export interface PerformanceWorkRun {
  id: number | string;
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
  estimatedCost?: number;
  roundNumber?: number | null;
  roundCount?: number | null;
  tokens?: number;
  modelName?: string;
  paidBy?: string;
}

export interface PerformanceReport {
  available: boolean;
  samples: PerformanceSample[];
  recentWork: PerformanceWorkRun[];
  error?: string;
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
