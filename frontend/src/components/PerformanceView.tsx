import { useMemo, useState } from "react";
import type { StatusPayload } from "../types";
import { formatBytes, formatInteger, formatNumber, formatPercent } from "../lib/format";
import { pointFromPerformanceSample, useStatusHistory } from "../hooks/useStatusHistory";
import { usePerformanceReport } from "../hooks/usePerformanceReport";
import { IngestStatusPanel } from "./IngestStatusPanel";
import { MetricBar } from "./MetricBar";
import { PerformanceChart } from "./PerformanceChart";
import { RecentWorkTable } from "./RecentWorkTable";
import { RuntimeBatchPanel } from "./RuntimeBatchPanel";
import { SectionHeader } from "./SectionHeader";
import { Stat } from "./Stat";

type ChartChoice = "utilization" | "memory" | "catalog" | "workers" | "all";

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
              <option value="catalog">Catalog growth</option>
              <option value="workers">Workers and batches</option>
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
              subtitle="System CPU, CircuitShelf process CPU, and GPU utilization."
              history={history}
              unit="%"
              series={[
                { key: "cpu", label: "System CPU", color: "#56b6ff" },
                { key: "processCpu", label: "Process CPU", color: "#62e6b5" },
                { key: "gpu", label: "GPU", color: "#ffb25f" },
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
                { key: "ram", label: "RAM", color: "#62e6b5" },
                { key: "vram", label: "VRAM", color: "#ffb25f" },
              ]}
            />
          ) : null}
          {showChart("catalog") ? (
            <PerformanceChart
              title="Catalog growth"
              subtitle="Indexed sources, text chunks, and image assets seen by status polling."
              history={history}
              series={[
                { key: "sources", label: "Sources", color: "#9aa7ff" },
                { key: "chunks", label: "Chunks", color: "#62e6b5" },
                { key: "images", label: "Images", color: "#ffb25f" },
              ]}
            />
          ) : null}
          {showChart("workers") ? (
            <PerformanceChart
              title="Active document workers"
              subtitle="How much document-level parallel work is currently in flight."
              history={history}
              series={[
                { key: "workers", label: "Active doc workers", color: "#62e6b5" },
              ]}
            />
          ) : null}
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
