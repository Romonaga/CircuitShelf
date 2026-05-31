import type { StatusPayload } from "../types";
import { formatBytes, formatInteger, formatNumber, formatPercent } from "../lib/format";
import { MetricBar } from "./MetricBar";

export function SidebarSystemCard({ status }: { status: StatusPayload | null }) {
  const resources = status?.systemResources;
  const gpu = resources?.gpu;
  const memory = resources?.memory;
  const process = resources?.process;
  const batches = status?.runtimeBatches;
  const workers = status?.ingestWorkerBudget;

  return (
    <section className="sidebar-system-card" aria-label="System load">
      <div className="sidebar-system-card-title">
        <span>System load</span>
        {status?.ingest?.running ? <strong>Indexing</strong> : <strong>Idle</strong>}
      </div>
      <MetricBar label="CPU" value={resources?.cpu?.utilizationPercent} tone="blue" />
      <MetricBar
        label="Process"
        value={process?.cpuPercent}
        max={Math.max(100, (resources?.cpu?.cores ?? 1) * 100)}
        detail={formatPercent(process?.cpuPercent)}
        tone="green"
      />
      <MetricBar label="RAM" value={memory?.usedPercent} detail={formatBytes(memory?.usedBytes)} tone="teal" />
      <MetricBar
        label="GPU"
        value={gpu?.available ? gpu.utilizationPercent : null}
        detail={gpu?.available ? formatPercent(gpu.utilizationPercent) : "n/a"}
        tone="orange"
      />
      <MetricBar
        label="VRAM"
        value={gpu?.available ? gpu.memoryUsedPercent : null}
        detail={gpu?.available ? `${formatNumber(gpu.memoryUsedMiB)} / ${formatNumber(gpu.memoryTotalMiB)} MiB` : "n/a"}
        tone="teal"
      />
      <div className="sidebar-system-pills">
        <span><small>Workers</small><strong>{formatInteger(workers?.activeDocumentWorkers)}</strong></span>
        <span><small>Emb</small><strong>{formatInteger(batches?.embedding?.active)}</strong></span>
        <span><small>Rank</small><strong>{formatInteger(batches?.reranker?.active)}</strong></span>
      </div>
    </section>
  );
}
