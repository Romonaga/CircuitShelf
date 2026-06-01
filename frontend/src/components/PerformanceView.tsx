import { useMemo, useState } from "react";
import type { StatusPayload } from "../types";
import { formatBytes, formatInteger, formatNumber, formatPercent } from "../lib/format";
import { pointFromPerformanceSample, useStatusHistory } from "../hooks/useStatusHistory";
import { chartColors } from "../lib/chartColors";
import { usePerformanceReport } from "../hooks/usePerformanceReport";
import { IngestStatusPanel } from "./IngestStatusPanel";
import { IngestionThroughputChart } from "./IngestionThroughputChart";
import { MetricBar } from "./MetricBar";
import { PerformanceChart } from "./PerformanceChart";
import { RecentWorkTable } from "./RecentWorkTable";
import { RuntimeBatchPanel } from "./RuntimeBatchPanel";
import { SectionHeader } from "./SectionHeader";
import { Stat } from "./Stat";
import { WorkDurationChart } from "./WorkDurationChart";

type ChartChoice =
  | "utilization"
  | "memory"
  | "processCpu"
  | "processMemory"
  | "processThreads"
  | "gpuTemperature"
  | "gpuPower"
  | "gpuMemory"
  | "gpuMemoryUsed"
  | "catalog"
  | "workers"
  | "batches"
  | "throughput"
  | "workDuration"
  | "all";

export function PerformanceView({
  status,
  refresh,
  isActive,
  onOpenReview
}: {
  status: StatusPayload | null;
  refresh: () => void;
  isActive: boolean;
  onOpenReview: () => void;
}) {
  const liveHistory = useStatusHistory(isActive ? status : null);
  const report = usePerformanceReport(isActive, 24, `${status?.systemResources?.sampledAt ?? ""}:${status?.ingest?.lastFinishedAt ?? ""}`);
  const [chartChoice, setChartChoice] = useState<ChartChoice>("utilization");
  const resources = status?.systemResources;
  const gpu = resources?.gpu;
  const memory = resources?.memory;
  const process = resources?.process;
  const showChart = (choice: ChartChoice) => chartChoice === "all" || chartChoice === choice;
  const processCpuMax = useMemo(() => Math.max(100, (resources?.cpu?.cores ?? 1) * 100), [resources?.cpu?.cores]);
  const persistedHistory = useMemo(
    () => (report.report?.samples ?? []).map(pointFromPerformanceSample),
    [report.report?.samples]
  );
  const history = persistedHistory.length ? persistedHistory : liveHistory;

  function refreshAll() {
    refresh();
    void report.refresh();
  }

  return (
    <section className="performance-page">
      <SectionHeader
        title="Performance"
        description="Runtime load, ingestion progress, GPU sizing, and catalog growth."
        actions={
          <div className="performance-actions">
            <select value={chartChoice} onChange={(event) => setChartChoice(event.target.value as ChartChoice)}>
              <option value="utilization">Utilization</option>
              <option value="memory">Memory</option>
              <option value="processCpu">Process CPU</option>
              <option value="processMemory">Process memory</option>
              <option value="processThreads">Process threads</option>
              <option value="gpuTemperature">GPU temperature</option>
              <option value="gpuPower">GPU power</option>
              <option value="gpuMemory">GPU memory %</option>
              <option value="gpuMemoryUsed">GPU memory MiB</option>
              <option value="catalog">Catalog growth</option>
              <option value="workers">Workers and CUDA batches</option>
              <option value="batches">Batch sizing</option>
              <option value="throughput">Ingestion throughput</option>
              <option value="workDuration">Work duration</option>
              <option value="all">All charts</option>
            </select>
            <button className="ghost-button" onClick={refreshAll}>Refresh</button>
          </div>
        }
      />
      {report.error ? <p className="error">{report.error}</p> : null}

      <div className="status-grid performance-stats">
        <Stat label="CPU cores" value={formatInteger(resources?.cpu?.cores)} />
        <Stat label="System CPU" value={formatPercent(resources?.cpu?.utilizationPercent)} />
        <Stat label="Process CPU" value={formatPercent(process?.cpuPercent)} />
        <Stat label="Process RAM" value={formatBytes(process?.memoryBytes)} />
        <Stat label="GPU" value={gpu?.available ? formatPercent(gpu.utilizationPercent) : "n/a"} />
        <Stat label="VRAM" value={gpu?.available ? `${formatNumber(gpu.memoryUsedMiB)} MiB` : "n/a"} />
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
          {showChart("utilization") ? (
            <PerformanceChart
              title="Utilization over time"
              subtitle="Same-unit utilization signals on a fixed 0-100% scale."
              fixedMin={0}
              fixedMax={100}
              history={history}
              unit="%"
              series={[
                { key: "cpu", label: "System CPU", color: chartColors.blue },
                { key: "gpu", label: "GPU", color: chartColors.orange },
              ]}
            />
          ) : null}
          {showChart("memory") ? (
            <PerformanceChart
              title="Memory pressure"
              subtitle="System RAM and GPU VRAM saturation."
              history={history}
              fixedMin={0}
              fixedMax={100}
              unit="%"
              series={[
                { key: "ram", label: "RAM", color: chartColors.green },
                { key: "vram", label: "VRAM", color: chartColors.orange },
              ]}
            />
          ) : null}
          {showChart("processCpu") ? (
            <PerformanceChart
              title="CircuitShelf process CPU"
              subtitle="Process CPU can exceed 100% because it spans multiple cores."
              history={history}
              fixedMin={0}
              fixedMax={processCpuMax}
              unit="%"
              series={[
                { key: "processCpu", label: "Process CPU", color: chartColors.green },
              ]}
            />
          ) : null}
          {showChart("processMemory") ? (
            <PerformanceChart
              title="CircuitShelf process memory"
              subtitle="Python process memory footprint in MiB."
              history={history}
              unit=" MiB"
              series={[
                { key: "processRamMiB", label: "Process RAM", color: chartColors.purple },
              ]}
            />
          ) : null}
          {showChart("processThreads") ? (
            <PerformanceChart
              title="CircuitShelf process threads"
              subtitle="Thread count helps spot OCR, ingestion, and server-worker pressure."
              history={history}
              series={[
                { key: "processThreads", label: "Threads", color: chartColors.blue },
              ]}
            />
          ) : null}
          {showChart("gpuTemperature") ? (
            <PerformanceChart
              title="GPU temperature"
              subtitle="Thermal trend while models, embeddings, and reranking run."
              history={history}
              unit=" C"
              series={[
                { key: "gpuTemp", label: "GPU temp", color: chartColors.vermillion },
              ]}
            />
          ) : null}
          {showChart("gpuPower") ? (
            <PerformanceChart
              title="GPU power"
              subtitle="Power draw trend during model, embedding, and reranker work."
              history={history}
              unit=" W"
              series={[
                { key: "gpuPower", label: "GPU power", color: chartColors.yellow },
              ]}
            />
          ) : null}
          {showChart("gpuMemory") ? (
            <PerformanceChart
              title="GPU memory saturation"
              subtitle="VRAM saturation on a fixed 0-100% scale."
              history={history}
              fixedMin={0}
              fixedMax={100}
              unit="%"
              series={[
                { key: "vram", label: "VRAM", color: chartColors.purple },
              ]}
            />
          ) : null}
          {showChart("gpuMemoryUsed") ? (
            <PerformanceChart
              title="GPU memory allocated"
              subtitle="Absolute VRAM use in MiB for model residency and batch work."
              history={history}
              unit=" MiB"
              series={[
                { key: "gpuMemoryMiB", label: "VRAM used", color: chartColors.orange },
              ]}
            />
          ) : null}
          {showChart("catalog") ? (
            <PerformanceChart
              title="Catalog growth"
              subtitle="Indexed sources, text chunks, and image assets seen by status polling."
              history={history}
              series={[
                { key: "sources", label: "Sources", color: chartColors.navy },
                { key: "chunks", label: "Chunks", color: chartColors.green },
                { key: "images", label: "Images", color: chartColors.orange },
              ]}
            />
          ) : null}
          {showChart("workers") ? (
            <PerformanceChart
              title="Active document workers"
              subtitle="Document workers plus the active embedding and reranker batch sizes."
              history={history}
              series={[
                { key: "workers", label: "Active doc workers", color: chartColors.green },
                { key: "embeddingBatch", label: "Embedding batch", color: chartColors.blue },
                { key: "rerankerBatch", label: "Reranker batch", color: chartColors.purple },
              ]}
            />
          ) : null}
          {showChart("batches") ? (
            <PerformanceChart
              title="Runtime batch sizing"
              subtitle="Embedding and reranker batch sizes selected from current hardware."
              history={history}
              series={[
                { key: "embeddingBatch", label: "Embedding batch", color: chartColors.blue },
                { key: "rerankerBatch", label: "Reranker batch", color: chartColors.purple },
              ]}
            />
          ) : null}
          {showChart("throughput") ? <IngestionThroughputChart rows={report.report?.recentWork ?? []} /> : null}
          {showChart("workDuration") ? <WorkDurationChart rows={report.report?.recentWork ?? []} /> : null}
        </div>
        <aside className="performance-side">
          <RuntimeBatchPanel batches={status?.runtimeBatches} />
          <IngestStatusPanel
            ingest={status?.ingest}
            workerBudget={status?.ingestWorkerBudget}
            pendingReview={status?.pendingReview}
            onOpenReview={onOpenReview}
          />
        </aside>
      </div>
      <RecentWorkTable rows={report.report?.recentWork ?? []} />
    </section>
  );
}
