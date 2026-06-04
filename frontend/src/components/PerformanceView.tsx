import { useMemo, useState } from "react";
import type { StatusPayload } from "../types";
import { pointFromPerformanceSample, useStatusHistory } from "../hooks/useStatusHistory";
import { usePerformanceReport } from "../hooks/usePerformanceReport";
import { IngestStatusPanel } from "./IngestStatusPanel";
import { LoadingSpinner } from "./LoadingSpinner";
import { RecentWorkTable } from "./RecentWorkTable";
import { RuntimeBatchPanel } from "./RuntimeBatchPanel";
import { SectionHeader } from "./SectionHeader";
import { PerformanceChartDeck } from "./performance/PerformanceChartDeck";
import { PerformanceChartSelector } from "./performance/PerformanceChartSelector";
import { PerformanceStatsGrid } from "./performance/PerformanceStatsGrid";
import { LiveResourcePressure } from "./performance/LiveResourcePressure";
import type { PerformanceChartChoice } from "./performance/chartTypes";

export function PerformanceView({
  status,
  isActive,
  onOpenReview
}: {
  status: StatusPayload | null;
  isActive: boolean;
  onOpenReview: () => void;
}) {
  const liveHistory = useStatusHistory(isActive ? status : null);
  const report = usePerformanceReport(isActive, 24, status?.ingest?.lastFinishedAt ?? "");
  const [chartChoice, setChartChoice] = useState<PerformanceChartChoice>("utilization");
  const [showIndexChecks, setShowIndexChecks] = useState(false);
  const resources = status?.systemResources;
  const runtimePeaks = resources?.peaks;
  const persistedHistory = useMemo(
    () => (report.report?.samples ?? []).map(pointFromPerformanceSample),
    [report.report?.samples]
  );
  const workerCapacity = Math.max(1, status?.ingestWorkerBudget?.usableCores ?? status?.ingestWorkerBudget?.activeDocumentWorkers ?? 1);
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
  const peakWorkers = Math.max(runtimePeaks?.activeDocumentWorkers ?? 0, peaks.workers ?? 0);
  const recentWork = report.report?.recentWork ?? [];
  const visibleRecentWork = showIndexChecks ? recentWork : recentWork.filter((row) => row.workType !== "index_check");
  const initialPerformanceLoad = report.loading && !report.report;

  return (
    <section className="performance-page">
      <SectionHeader
        title="Performance"
        description="Runtime load, ingestion progress, GPU sizing, and completed work output."
      />
      {report.error ? <p className="error">{report.error}</p> : null}
      {report.loading ? (
        <div className="performance-loading-banner" role="status" aria-live="polite">
          <LoadingSpinner />
          <div>
            <strong>{initialPerformanceLoad ? "Loading performance history" : "Refreshing performance history"}</strong>
            <span>Live status keeps updating while the historical samples and work runs load.</span>
          </div>
        </div>
      ) : null}

      <PerformanceStatsGrid resources={resources} peaks={peaks} peakWorkers={peakWorkers} />
      <LiveResourcePressure resources={resources} />

      <div className="performance-layout">
        <div className="performance-main">
          <PerformanceChartSelector value={chartChoice} onChange={setChartChoice} />
          <PerformanceChartDeck
            chartChoice={chartChoice}
            history={history}
            visibleRecentWork={visibleRecentWork}
            loadingInitial={initialPerformanceLoad}
          />
        </div>
        <aside className="performance-side">
          <RuntimeBatchPanel batches={status?.runtimeBatches} />
          <IngestStatusPanel
            ingest={status?.ingest}
            workerBudget={status?.ingestWorkerBudget}
            runtimeBatches={status?.runtimeBatches}
            pendingReview={status?.pendingReview}
            onOpenReview={onOpenReview}
          />
        </aside>
      </div>
      <RecentWorkTable rows={visibleRecentWork} showIndexChecks={showIndexChecks} onShowIndexChecksChange={setShowIndexChecks} />
    </section>
  );
}

function maxHistoryValue<K extends keyof ReturnType<typeof pointFromPerformanceSample>>(
  history: ReturnType<typeof pointFromPerformanceSample>[],
  key: K
): number | null {
  const values = history
    .map((point) => point[key])
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  return values.length ? Math.max(...values) : null;
}

function mergeHistory(
  persistedHistory: ReturnType<typeof pointFromPerformanceSample>[],
  liveHistory: ReturnType<typeof pointFromPerformanceSample>[]
) {
  const bySampleTime = new Map<number, ReturnType<typeof pointFromPerformanceSample>>();
  persistedHistory.forEach((point) => bySampleTime.set(point.sampledAt, point));
  liveHistory.forEach((point) => bySampleTime.set(point.sampledAt, point));
  return Array.from(bySampleTime.values())
    .sort((left, right) => left.sampledAt - right.sampledAt)
    .slice(-500);
}

function normalizeHistoryWorkerLoad(
  history: ReturnType<typeof pointFromPerformanceSample>[],
  workerCapacity: number
) {
  return history.map((point) => {
    if (typeof point.workerLoad === "number") {
      return point;
    }
    return {
      ...point,
      workerLoad: point.workers ? Math.min(100, (point.workers / workerCapacity) * 100) : 0,
    };
  });
}
