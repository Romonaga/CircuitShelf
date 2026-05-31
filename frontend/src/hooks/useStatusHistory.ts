import { useEffect, useState } from "react";
import type { PerformanceSample, StatusPayload } from "../types";

export interface StatusHistoryPoint {
  sampledAt: number;
  cpu: number | null;
  processCpu: number | null;
  ram: number | null;
  gpu: number | null;
  vram: number | null;
  gpuTemp: number | null;
  gpuPower: number | null;
  processRamMiB: number | null;
  embeddingBatch: number;
  rerankerBatch: number;
  chunks: number;
  sources: number;
  images: number;
  workers: number;
}

export function pointFromPerformanceSample(sample: PerformanceSample): StatusHistoryPoint {
  const sampled = sample.sampledAt ? Date.parse(sample.sampledAt) : Date.now();
  return {
    sampledAt: Number.isFinite(sampled) ? sampled : Date.now(),
    cpu: sample.cpu ?? null,
    processCpu: sample.processCpu ?? null,
    ram: sample.ram ?? null,
    gpu: sample.gpu ?? null,
    vram: sample.vram ?? null,
    gpuTemp: sample.gpuTemperatureC ?? null,
    gpuPower: sample.gpuPowerW ?? null,
    processRamMiB: sample.processMemoryBytes ? sample.processMemoryBytes / (1024 * 1024) : null,
    embeddingBatch: sample.embeddingBatch ?? 0,
    rerankerBatch: sample.rerankerBatch ?? 0,
    chunks: sample.chunks ?? 0,
    sources: sample.sources ?? 0,
    images: sample.images ?? 0,
    workers: sample.workers ?? 0,
  };
}

function pointFromStatus(status: StatusPayload): StatusHistoryPoint {
  const sampled = status.systemResources?.sampledAt ? Date.parse(status.systemResources.sampledAt) : Date.now();
  return {
    sampledAt: Number.isFinite(sampled) ? sampled : Date.now(),
    cpu: status.systemResources?.cpu?.utilizationPercent ?? null,
    processCpu: status.systemResources?.process?.cpuPercent ?? null,
    ram: status.systemResources?.memory?.usedPercent ?? null,
    gpu: status.systemResources?.gpu?.available ? status.systemResources.gpu.utilizationPercent ?? null : null,
    vram: status.systemResources?.gpu?.available ? status.systemResources.gpu.memoryUsedPercent ?? null : null,
    gpuTemp: status.systemResources?.gpu?.available ? status.systemResources.gpu.temperatureC ?? null : null,
    gpuPower: status.systemResources?.gpu?.available ? status.systemResources.gpu.powerW ?? null : null,
    processRamMiB: status.systemResources?.process?.memoryBytes ? status.systemResources.process.memoryBytes / (1024 * 1024) : null,
    embeddingBatch: status.runtimeBatches?.embedding?.active ?? 0,
    rerankerBatch: status.runtimeBatches?.reranker?.active ?? 0,
    chunks: status.chunks ?? 0,
    sources: status.sources ?? 0,
    images: status.imageIds ?? 0,
    workers: status.ingestWorkerBudget?.activeDocumentWorkers ?? 0,
  };
}

export function useStatusHistory(status: StatusPayload | null, maxPoints = 180) {
  const [history, setHistory] = useState<StatusHistoryPoint[]>([]);

  useEffect(() => {
    if (!status) {
      return;
    }
    const next = pointFromStatus(status);
    setHistory((current) => {
      const previous = current[current.length - 1];
      if (previous && Math.abs(previous.sampledAt - next.sampledAt) < 250) {
        return current;
      }
      return [...current, next].slice(-maxPoints);
    });
  }, [maxPoints, status]);

  return history;
}
