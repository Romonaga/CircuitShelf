import type { RuntimeBatchStatus, StatusPayload } from "../types";
import { formatBytes, formatInteger, formatNumber, formatPercent } from "../libs/format";
import { MetricBar } from "./MetricBar";

function batchDetail(batch: RuntimeBatchStatus | undefined): string {
  if (!batch) {
    return "n/a";
  }
  const mode = batch.auto ? "auto" : "manual";
  return `${mode} | configured ${formatInteger(batch.configured)} | recommended ${formatInteger(batch.recommended)}`;
}

function currentAndPeak(current?: number | null, peak?: number | null) {
  const currentText = formatPercent(current);
  return peak == null ? currentText : `${currentText} / today ${formatPercent(peak)}`;
}

function formatShortTime(value?: string | null) {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function SidebarSystemCard({ status, detailed = false }: { status: StatusPayload | null; detailed?: boolean }) {
  const resources = status?.systemResources;
  const gpu = resources?.gpu;
  const memory = resources?.memory;
  const process = resources?.process;
  const peaks = resources?.peaks;
  const batches = status?.runtimeBatches;
  const workers = status?.ingestWorkerBudget;
  const workerCapacity = workers?.documentWorkerCapacity ?? workers?.activeDocumentWorkers;
  const ingest = status?.ingest;
  const ingestProgress = ingest?.totalFiles
    ? `${formatInteger(ingest.processedFiles)} / ${formatInteger(ingest.totalFiles)} files`
    : ingest?.running
      ? "running"
      : "idle";

  return (
    <section className="sidebar-system-card" aria-label="System load">
      <div className="sidebar-system-card-title">
        <span>System load</span>
        {status?.ingest?.running ? <strong>Indexing</strong> : <strong>Idle</strong>}
      </div>
      <MetricBar
        label="CPU"
        value={resources?.cpu?.utilizationPercent}
        detail={currentAndPeak(resources?.cpu?.utilizationPercent, peaks?.cpuPercent)}
        tone="blue"
      />
      <MetricBar
        label="Process"
        value={process?.cpuPercent}
        max={Math.max(100, (resources?.cpu?.cores ?? 1) * 100)}
        detail={currentAndPeak(process?.cpuPercent, peaks?.processCpuPercent)}
        tone="green"
      />
      <MetricBar
        label="RAM"
        value={memory?.usedPercent}
        detail={peaks?.memoryUsedPercent == null ? formatBytes(memory?.usedBytes) : `${formatPercent(memory?.usedPercent)} / today ${formatPercent(peaks.memoryUsedPercent)}`}
        tone="teal"
      />
      <MetricBar
        label="GPU"
        value={gpu?.available ? gpu.utilizationPercent : null}
        detail={gpu?.available ? currentAndPeak(gpu.utilizationPercent, peaks?.gpuPercent) : "n/a"}
        tone="orange"
      />
      <MetricBar
        label="VRAM"
        value={gpu?.available ? gpu.memoryUsedPercent : null}
        detail={gpu?.available ? `${formatNumber(gpu.memoryUsedMiB)} MiB / today ${formatPercent(peaks?.gpuMemoryUsedPercent)}` : "n/a"}
        tone="teal"
      />
      <div className="sidebar-system-pills">
        <span><small>Workers</small><strong>{formatInteger(workers?.activeDocumentWorkers)} / {formatInteger(workerCapacity)}</strong></span>
        <span><small>Emb</small><strong>{formatInteger(batches?.embedding?.active)}</strong></span>
        <span><small>Rank</small><strong>{formatInteger(batches?.reranker?.active)}</strong></span>
      </div>
      {detailed ? (
        <div className="sidebar-system-detail">
          <div className="system-detail-row wide">
            <span>GPU</span>
            <strong title={gpu?.name || "No GPU detected"}>{gpu?.available ? gpu.name : "n/a"}</strong>
          </div>
          <div className="system-detail-grid">
            <span><small>Sources</small><strong>{formatInteger(status?.sources)}</strong></span>
            <span><small>Chunks</small><strong>{formatInteger(status?.chunks)}</strong></span>
            <span><small>Images</small><strong>{formatInteger(status?.imageIds)}</strong></span>
            <span><small>Review</small><strong>{formatInteger(status?.pendingReview)}</strong></span>
            <span><small>Ingest</small><strong>{ingestProgress}</strong></span>
            <span><small>Next check</small><strong>{formatShortTime(ingest?.nextCheckAt)}</strong></span>
            <span><small>Temp</small><strong>{gpu?.temperatureC == null ? "n/a" : `${formatNumber(gpu.temperatureC)} C`}</strong></span>
            <span><small>Power</small><strong>{gpu?.powerW == null ? "n/a" : `${formatNumber(gpu.powerW)} W`}</strong></span>
            <span><small>CPU cores</small><strong>{formatInteger(resources?.cpu?.cores)}</strong></span>
            <span><small>Threads</small><strong>{formatInteger(process?.threads)}</strong></span>
            <span><small>Proc RAM</small><strong>{formatBytes(process?.memoryBytes)}</strong></span>
            <span><small>Usable cores</small><strong>{formatInteger(workers?.usableCores)}</strong></span>
            <span><small>Worker slots</small><strong>{formatInteger(workerCapacity)}</strong></span>
            <span><small>Today workers</small><strong>{formatInteger(peaks?.activeDocumentWorkers)}</strong></span>
            <span><small>Today GPU temp</small><strong>{peaks?.gpuTemperatureC == null ? "n/a" : `${formatNumber(peaks.gpuTemperatureC)} C`}</strong></span>
          </div>
          <div className="system-batch-detail">
            <div>
              <span>Embedding</span>
              <strong>{formatInteger(batches?.embedding?.active)} batch · {batches?.embedding?.device || "device n/a"}</strong>
              <small title={batches?.embedding?.model || ""}>{batches?.embedding?.model || "Model not configured"}</small>
              <em>{batchDetail(batches?.embedding)}</em>
            </div>
            <div>
              <span>Reranker</span>
              <strong>{formatInteger(batches?.reranker?.active)} batch · {batches?.reranker?.device || "device n/a"}</strong>
              <small title={batches?.reranker?.model || ""}>{batches?.reranker?.model || "Model not configured"}</small>
              <em>{batchDetail(batches?.reranker)}</em>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
