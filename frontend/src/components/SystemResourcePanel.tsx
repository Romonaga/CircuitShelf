import type { LocalGpuQueueStatus, SystemResources } from "../types/status";
import { formatBytes, formatInteger, formatNumber, formatPercent } from "../libs/format";

function queueCount(queue: LocalGpuQueueStatus | null | undefined, resource: string, status: string) {
  return queue?.byResource?.[resource]?.[status] ?? 0;
}

function queueWait(queue: LocalGpuQueueStatus | null | undefined) {
  const wait = queue?.wait?.currentMaxWaitSeconds;
  return wait == null ? "n/a" : `${formatNumber(wait)}s`;
}

function memoryLabel(resources?: SystemResources | null) {
  const used = resources?.memory?.usedBytes;
  const total = resources?.memory?.totalBytes;
  if (used == null || total == null) {
    return formatPercent(resources?.memory?.usedPercent);
  }
  return `${formatBytes(used)} / ${formatBytes(total)}`;
}

function gpuMemoryLabel(resources?: SystemResources | null) {
  const gpu = resources?.gpu;
  if (!gpu?.available) {
    return "n/a";
  }
  if (gpu.memoryUsedMiB == null || gpu.memoryTotalMiB == null) {
    return formatPercent(gpu.memoryUsedPercent);
  }
  return `${formatInteger(gpu.memoryUsedMiB)} / ${formatInteger(gpu.memoryTotalMiB)} MiB`;
}

export function SystemResourcePanel({
  resources,
  queue,
}: {
  resources?: SystemResources | null;
  queue?: LocalGpuQueueStatus | null;
}) {
  const process = resources?.process;
  const gpu = resources?.gpu;
  const gpuQueued = queue?.queued ?? 0;
  const gpuRunning = queue?.active ?? 0;

  return (
    <div className="system-resource-panel">
      <section className="resource-group-card">
        <div className="resource-group-heading">
          <span>CPU and memory</span>
          <strong>{formatInteger(resources?.cpu?.cores)} cores</strong>
        </div>
        <div className="resource-metric-grid">
          <span><small>System CPU</small><strong>{formatPercent(resources?.cpu?.utilizationPercent)}</strong></span>
          <span><small>App CPU</small><strong>{formatPercent(process?.cpuPercent)}</strong></span>
          <span><small>RAM</small><strong>{memoryLabel(resources)}</strong></span>
          <span><small>App RAM</small><strong>{formatBytes(process?.memoryBytes)}</strong></span>
          <span><small>Threads</small><strong>{formatInteger(process?.threads)}</strong></span>
          <span><small>CPU temp</small><strong>{resources?.cpu?.temperatureC == null ? "n/a" : `${formatNumber(resources.cpu.temperatureC)} C`}</strong></span>
        </div>
      </section>

      <section className="resource-group-card gpu">
        <div className="resource-group-heading">
          <span>GPU and local queue</span>
          <strong>{gpu?.available ? gpu.name : "No GPU detected"}</strong>
        </div>
        <div className="resource-metric-grid">
          <span><small>GPU load</small><strong>{gpu?.available ? formatPercent(gpu.utilizationPercent) : "n/a"}</strong></span>
          <span><small>VRAM</small><strong>{gpuMemoryLabel(resources)}</strong></span>
          <span><small>Power</small><strong>{gpu?.available && gpu.powerW != null ? `${formatNumber(gpu.powerW)} W` : "n/a"}</strong></span>
          <span><small>Temp</small><strong>{gpu?.available && gpu.temperatureC != null ? `${formatNumber(gpu.temperatureC)} C` : "n/a"}</strong></span>
          <span><small>Queue</small><strong>{formatInteger(gpuRunning)} active / {formatInteger(gpuQueued)} queued</strong></span>
          <span><small>Oldest wait</small><strong>{queueWait(queue)}</strong></span>
        </div>
        <div className="resource-queue-grid">
          <span><small>LLM</small><strong>{formatInteger(queueCount(queue, "local_llm", "running"))} / {formatInteger(queueCount(queue, "local_llm", "queued"))}</strong></span>
          <span><small>CUDA</small><strong>{formatInteger(queueCount(queue, "cuda_batch", "running"))} / {formatInteger(queueCount(queue, "cuda_batch", "queued"))}</strong></span>
          <span><small>OCR</small><strong>{formatInteger(queueCount(queue, "ocr_cuda", "running"))} / {formatInteger(queueCount(queue, "ocr_cuda", "queued"))}</strong></span>
        </div>
      </section>
    </div>
  );
}
