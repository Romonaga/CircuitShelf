import { useMemo } from "react";
import { useStatusHistory } from "../useStatusHistory";
import {
  maxHistoryValue,
  mergeHistory,
  normalizeHistoryWorkerLoad,
  pointFromPerformanceSample,
} from "../../libs/performance/history";
import type { PerformanceSample, StatusPayload } from "../../types";

export function usePerformanceHistory({
  isActive,
  status,
  reportSamples
}: {
  isActive: boolean;
  status: StatusPayload | null;
  reportSamples: PerformanceSample[] | undefined;
}) {
  const liveHistory = useStatusHistory(isActive ? status : null);
  const persistedHistory = useMemo(
    () => (reportSamples ?? []).map(pointFromPerformanceSample),
    [reportSamples]
  );
  const workerCapacity = Math.max(
    1,
    status?.ingestWorkerBudget?.documentWorkerCapacity
      ?? status?.ingestWorkerBudget?.activeDocumentWorkers
      ?? 1
  );
  const history = useMemo(
    () => normalizeHistoryWorkerLoad(mergeHistory(persistedHistory, liveHistory), workerCapacity),
    [liveHistory, persistedHistory, workerCapacity]
  );
  const peaks = useMemo(() => ({
    cpu: maxHistoryValue(history, "cpu"),
    processCpu: maxHistoryValue(history, "processCpu"),
    gpu: maxHistoryValue(history, "gpu"),
    cpuTemp: maxHistoryValue(history, "cpuTemp"),
    gpuTemp: maxHistoryValue(history, "gpuTemp"),
    vram: maxHistoryValue(history, "vram"),
    workers: maxHistoryValue(history, "workers"),
    processRamMiB: maxHistoryValue(history, "processRamMiB"),
  }), [history]);

  return { history, peaks };
}
