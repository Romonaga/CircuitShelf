import type { PerformanceSample, StatusPayload } from "../../types";

export interface StatusHistoryPoint {
  sampledAt: number;
  cpu: number | null;
  cpuTemp: number | null;
  cpuPower: number | null;
  processCpu: number | null;
  ram: number | null;
  gpu: number | null;
  vram: number | null;
  gpuTemp: number | null;
  gpuPower: number | null;
  processRamMiB: number | null;
  processRam: number | null;
  processThreads: number | null;
  gpuMemoryMiB: number | null;
  processCpuLoad: number | null;
  cpuTempLoad: number | null;
  workerLoad: number | null;
  gpuTempLoad: number | null;
  gpuPowerLoad: number | null;
  embeddingBatch: number;
  rerankerBatch: number;
  chunks: number;
  sources: number;
  images: number;
  workers: number;
  workerCapacity: number;
}

export function pointFromPerformanceSample(sample: PerformanceSample): StatusHistoryPoint {
  const sampled = sample.sampledAt ? Date.parse(sample.sampledAt) : Date.now();
  return {
    sampledAt: Number.isFinite(sampled) ? sampled : Date.now(),
    cpu: sample.cpu ?? null,
    cpuTemp: sample.cpuTemperatureC ?? null,
    cpuPower: sample.cpuPowerW ?? null,
    processCpu: sample.processCpu ?? null,
    ram: sample.ram ?? null,
    gpu: sample.gpu ?? null,
    vram: sample.vram ?? null,
    gpuTemp: sample.gpuTemperatureC ?? null,
    gpuPower: sample.gpuPowerW ?? null,
    processRamMiB: sample.processMemoryBytes ? sample.processMemoryBytes / (1024 * 1024) : null,
    processRam: null,
    processThreads: sample.processThreads ?? null,
    gpuMemoryMiB: sample.gpuMemoryUsedMiB ?? null,
    processCpuLoad: null,
    cpuTempLoad: sample.cpuTemperatureC ? Math.min(100, (sample.cpuTemperatureC / 95) * 100) : null,
    workerLoad: null,
    gpuTempLoad: sample.gpuTemperatureC ? Math.min(100, (sample.gpuTemperatureC / 90) * 100) : null,
    gpuPowerLoad: sample.gpuPowerW ? Math.min(100, (sample.gpuPowerW / 450) * 100) : null,
    embeddingBatch: sample.embeddingBatch ?? 0,
    rerankerBatch: sample.rerankerBatch ?? 0,
    chunks: sample.chunks ?? 0,
    sources: sample.sources ?? 0,
    images: sample.images ?? 0,
    workers: sample.workers ?? 0,
    workerCapacity: sample.workerCapacity ?? 0,
  };
}

export function pointFromStatus(status: StatusPayload): StatusHistoryPoint {
  const sampled = status.systemResources?.sampledAt ? Date.parse(status.systemResources.sampledAt) : Date.now();
  const processRamMiB = status.systemResources?.process?.memoryBytes ? status.systemResources.process.memoryBytes / (1024 * 1024) : null;
  const totalRamMiB = status.systemResources?.memory?.totalBytes ? status.systemResources.memory.totalBytes / (1024 * 1024) : null;
  const processCpuMax = Math.max(100, (status.systemResources?.cpu?.cores ?? 1) * 100);
  const activeDocumentWorkers = status.ingestWorkerBudget?.activeDocumentWorkers ?? 0;
  const workerCapacity = Math.max(
    0,
    status.ingestWorkerBudget?.documentWorkerCapacity ?? activeDocumentWorkers
  );
  return {
    sampledAt: Number.isFinite(sampled) ? sampled : Date.now(),
    cpu: status.systemResources?.cpu?.utilizationPercent ?? null,
    cpuTemp: status.systemResources?.cpu?.temperatureC ?? null,
    cpuPower: status.systemResources?.cpu?.powerW ?? null,
    processCpu: status.systemResources?.process?.cpuPercent ?? null,
    ram: status.systemResources?.memory?.usedPercent ?? null,
    gpu: status.systemResources?.gpu?.available ? status.systemResources.gpu.utilizationPercent ?? null : null,
    vram: status.systemResources?.gpu?.available ? status.systemResources.gpu.memoryUsedPercent ?? null : null,
    gpuTemp: status.systemResources?.gpu?.available ? status.systemResources.gpu.temperatureC ?? null : null,
    gpuPower: status.systemResources?.gpu?.available ? status.systemResources.gpu.powerW ?? null : null,
    processRamMiB,
    processRam: processRamMiB && totalRamMiB ? (processRamMiB / totalRamMiB) * 100 : null,
    processThreads: status.systemResources?.process?.threads ?? null,
    gpuMemoryMiB: status.systemResources?.gpu?.available ? status.systemResources.gpu.memoryUsedMiB ?? null : null,
    processCpuLoad:
      typeof status.systemResources?.process?.cpuPercent === "number"
        ? Math.min(100, (status.systemResources.process.cpuPercent / processCpuMax) * 100)
        : null,
    cpuTempLoad: typeof status.systemResources?.cpu?.temperatureC === "number"
      ? Math.min(100, (status.systemResources.cpu.temperatureC / 95) * 100)
      : null,
    workerLoad: activeDocumentWorkers && workerCapacity
      ? Math.min(100, (activeDocumentWorkers / workerCapacity) * 100)
      : 0,
    gpuTempLoad: status.systemResources?.gpu?.available && typeof status.systemResources.gpu.temperatureC === "number"
      ? Math.min(100, (status.systemResources.gpu.temperatureC / 90) * 100)
      : null,
    gpuPowerLoad: status.systemResources?.gpu?.available && typeof status.systemResources.gpu.powerW === "number"
      ? Math.min(100, (status.systemResources.gpu.powerW / 450) * 100)
      : null,
    embeddingBatch: status.runtimeBatches?.embedding?.active ?? 0,
    rerankerBatch: status.runtimeBatches?.reranker?.active ?? 0,
    chunks: status.chunks ?? 0,
    sources: status.sources ?? 0,
    images: status.imageIds ?? 0,
    workers: activeDocumentWorkers,
    workerCapacity,
  };
}

export function maxHistoryValue<K extends keyof StatusHistoryPoint>(
  history: StatusHistoryPoint[],
  key: K
): number | null {
  const values = history
    .map((point) => point[key])
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  return values.length ? Math.max(...values) : null;
}

export function mergeHistory(
  persistedHistory: StatusHistoryPoint[],
  liveHistory: StatusHistoryPoint[]
) {
  const bySampleTime = new Map<number, StatusHistoryPoint>();
  persistedHistory.forEach((point) => bySampleTime.set(point.sampledAt, point));
  liveHistory.forEach((point) => bySampleTime.set(point.sampledAt, point));
  return Array.from(bySampleTime.values())
    .sort((left, right) => left.sampledAt - right.sampledAt)
    .slice(-500);
}

export function normalizeHistoryWorkerLoad(
  history: StatusHistoryPoint[],
  workerCapacity: number
) {
  return history.map((point) => {
    if (typeof point.workerLoad === "number") {
      return point;
    }
    return {
      ...point,
      workerLoad: point.workers ? Math.min(100, (point.workers / Math.max(1, point.workerCapacity || workerCapacity)) * 100) : 0,
    };
  });
}
