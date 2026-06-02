import { useMemo, useState } from "react";
import type { StatusPayload } from "../types";
import { formatBytes, formatInteger, formatNumber, formatPercent } from "../lib/format";
import { pointFromPerformanceSample, useStatusHistory } from "../hooks/useStatusHistory";
import { usePerformanceReport } from "../hooks/usePerformanceReport";
import { IngestStatusPanel } from "./IngestStatusPanel";
import { IngestionThroughputChart } from "./IngestionThroughputChart";
import { LoadingSpinner } from "./LoadingSpinner";
import { MetricBar } from "./MetricBar";
import { RecentWorkTable } from "./RecentWorkTable";
import { RuntimeBatchPanel } from "./RuntimeBatchPanel";
import { SectionHeader } from "./SectionHeader";
import { Stat } from "./Stat";
import { WorkDurationChart } from "./WorkDurationChart";
import { BatchEfficiencyGraph } from "./performanceCharts/BatchEfficiencyGraph";
import { CatalogGrowthGraph } from "./performanceCharts/CatalogGrowthGraph";
import { GpuEnvelopeGraph } from "./performanceCharts/GpuEnvelopeGraph";
import { IngestionOutcomeGraph } from "./performanceCharts/IngestionOutcomeGraph";
import { PowerGraph } from "./performanceCharts/PowerGraph";
import { ThermalGraph } from "./performanceCharts/ThermalGraph";
import { UtilizationGraph } from "./performanceCharts/UtilizationGraph";
import { WorkerBatchGraph } from "./performanceCharts/WorkerBatchGraph";

type ChartChoice =
  | "utilization"
  | "gpuEnvelope"
  | "thermals"
  | "power"
  | "catalog"
  | "workers"
  | "ingestionWork"
  | "all";

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
  const [chartChoice, setChartChoice] = useState<ChartChoice>("utilization");
  const [showIndexChecks, setShowIndexChecks] = useState(false);
  const resources = status?.systemResources;
  const gpu = resources?.gpu;
  const memory = resources?.memory;
  const process = resources?.process;
  const runtimePeaks = resources?.peaks;
  const showChart = (choice: ChartChoice) => chartChoice === "all" || chartChoice === choice;
  const processCpuMax = useMemo(() => Math.max(100, (resources?.cpu?.cores ?? 1) * 100), [resources?.cpu?.cores]);
  const persistedHistory = useMemo(
    () => (report.report?.samples ?? []).map(pointFromPerformanceSample),
    [report.report?.samples]
  );
  const history = useMemo(() => mergeHistory(persistedHistory, liveHistory), [liveHistory, persistedHistory]);
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
        description="Runtime load, ingestion progress, GPU sizing, and catalog growth."
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

      <div className="status-grid performance-stats">
        <Stat label="CPU cores" value={formatInteger(resources?.cpu?.cores)} />
        <Stat label="System CPU" value={formatPercent(resources?.cpu?.utilizationPercent)} />
        <Stat label="Process CPU" value={formatPercent(process?.cpuPercent)} />
        <Stat label="Process RAM" value={formatBytes(process?.memoryBytes)} />
        <Stat label="CPU temp" value={typeof resources?.cpu?.temperatureC === "number" ? `${formatNumber(resources.cpu.temperatureC)} C` : "n/a"} />
        <Stat label="CPU power" value={typeof resources?.cpu?.powerW === "number" ? `${formatNumber(resources.cpu.powerW)} W` : "n/a"} />
        <Stat label="GPU" value={gpu?.available ? formatPercent(gpu.utilizationPercent) : "n/a"} />
        <Stat label="GPU temp" value={gpu?.available && typeof gpu.temperatureC === "number" ? `${formatNumber(gpu.temperatureC)} C` : "n/a"} />
        <Stat label="GPU power" value={gpu?.available && typeof gpu.powerW === "number" ? `${formatNumber(gpu.powerW)} W` : "n/a"} />
        <Stat label="VRAM" value={gpu?.available ? `${formatNumber(gpu.memoryUsedMiB)} MiB` : "n/a"} />
        <Stat label="Window peak CPU" value={formatPercent(peaks.cpu)} />
        <Stat label="Window peak GPU" value={formatPercent(peaks.gpu)} />
        <Stat label="Runtime peak CPU" value={formatPercent(runtimePeaks?.cpuPercent)} />
        <Stat label="Runtime peak CPU temp" value={typeof runtimePeaks?.cpuTemperatureC === "number" ? `${formatNumber(runtimePeaks.cpuTemperatureC)} C` : "n/a"} />
        <Stat label="Runtime peak CPU power" value={typeof runtimePeaks?.cpuPowerW === "number" ? `${formatNumber(runtimePeaks.cpuPowerW)} W` : "n/a"} />
        <Stat label="Runtime peak process" value={formatPercent(runtimePeaks?.processCpuPercent)} />
        <Stat label="Runtime peak GPU" value={formatPercent(runtimePeaks?.gpuPercent)} />
        <Stat label="Runtime peak GPU temp" value={typeof runtimePeaks?.gpuTemperatureC === "number" ? `${formatNumber(runtimePeaks.gpuTemperatureC)} C` : "n/a"} />
        <Stat label="Runtime peak VRAM" value={formatPercent(runtimePeaks?.gpuMemoryUsedPercent)} />
        <Stat label="Peak doc workers" value={formatInteger(peakWorkers)} />
        <Stat label="Runtime peak RAM" value={formatPercent(runtimePeaks?.memoryUsedPercent)} />
      </div>

      <section className="resource-panel">
        <div>
          <h3>Live resource pressure</h3>
          <p>{gpu?.available ? gpu.name : "No NVIDIA telemetry available"}</p>
        </div>
        <MetricBar label="CPU" value={resources?.cpu?.utilizationPercent} tone="blue" />
        <MetricBar label="Process CPU" value={process?.cpuPercent} max={processCpuMax} tone="green" />
        <MetricBar label="RAM" value={memory?.usedPercent} detail={`${formatBytes(memory?.usedBytes)} / ${formatBytes(memory?.totalBytes)}`} tone="teal" />
        <MetricBar label="GPU" value={gpu?.available ? gpu.utilizationPercent : null} tone="orange" />
        <MetricBar
          label="VRAM"
          value={gpu?.available ? gpu.memoryUsedPercent : null}
          detail={gpu?.available ? `${formatNumber(gpu.memoryUsedMiB)} / ${formatNumber(gpu.memoryTotalMiB)} MiB` : "n/a"}
          tone="teal"
        />
      </section>

      <div className="performance-layout">
        <div className="performance-main">
          <div className="chart-toolbar">
            <label>
              <span>Graph</span>
              <select value={chartChoice} onChange={(event) => setChartChoice(event.target.value as ChartChoice)}>
                <option value="utilization">Utilization</option>
                <option value="gpuEnvelope">GPU envelope</option>
                <option value="thermals">Thermals</option>
                <option value="power">Power</option>
                <option value="catalog">Catalog growth</option>
                <option value="workers">Workers and CUDA batches</option>
                <option value="ingestionWork">Ingestion work health</option>
                <option value="all">All charts</option>
              </select>
            </label>
          </div>
          {initialPerformanceLoad && history.length === 0 ? (
            <section className="performance-chart-card performance-report-loading">
              <LoadingSpinner />
              <div>
                <h3>Preparing charts</h3>
                <p>Fetching persisted resource samples, recent work runs, and chart modules.</p>
              </div>
            </section>
          ) : null}
          {showChart("utilization") ? <UtilizationGraph history={history} /> : null}
          {showChart("gpuEnvelope") ? <GpuEnvelopeGraph history={history} /> : null}
          {showChart("thermals") ? <ThermalGraph history={history} /> : null}
          {showChart("power") ? <PowerGraph history={history} /> : null}
          {showChart("catalog") ? <CatalogGrowthGraph history={history} /> : null}
          {showChart("workers") ? <WorkerBatchGraph history={history} /> : null}
          {showChart("workers") ? <BatchEfficiencyGraph history={history} /> : null}
          {showChart("ingestionWork") ? (
            <>
              <IngestionOutcomeGraph rows={visibleRecentWork} />
              <IngestionThroughputChart rows={visibleRecentWork} />
              <WorkDurationChart rows={visibleRecentWork} />
            </>
          ) : null}
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
