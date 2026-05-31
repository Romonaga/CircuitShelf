import { useEffect, useState } from "react";
import type { StatusPayload } from "../types";

export interface StatusHistoryPoint {
  sampledAt: number;
  cpu: number | null;
  processCpu: number | null;
  ram: number | null;
  gpu: number | null;
  vram: number | null;
  chunks: number;
  sources: number;
  images: number;
  workers: number;
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
