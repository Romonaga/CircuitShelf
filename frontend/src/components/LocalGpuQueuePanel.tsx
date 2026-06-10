import type { LocalGpuQueueItem, LocalGpuQueueStatus } from "../types/status";
import { formatInteger, formatNumber } from "../libs/format";

const RESOURCE_LABELS: Record<string, string> = {
  cuda_batch: "CUDA batch",
  local_llm: "Local LLM",
  ocr_cuda: "OCR CUDA",
};

const TASK_LABELS: Record<string, string> = {
  embedding: "Embedding",
  local_llm: "Local LLM",
  paddleocr: "PaddleOCR",
  rerank: "Reranker",
};

function resourceLabel(resource?: string | null) {
  const key = String(resource || "").toLowerCase();
  return RESOURCE_LABELS[key] || key || "Unknown";
}

function taskLabel(taskType?: string | null) {
  const key = String(taskType || "").toLowerCase();
  return TASK_LABELS[key] || taskType || "Unknown";
}

function queueItemLabel(item: LocalGpuQueueItem) {
  const owner = item.owner ? `${item.owner} · ` : "";
  return `${owner}${taskLabel(item.taskType)}`;
}

function queueDetail(item: LocalGpuQueueItem) {
  const details = item.details || {};
  const items = details.items;
  const width = details.width;
  const height = details.height;
  const model = details.model;
  const size = typeof width === "number" && typeof height === "number" ? `${width}x${height}` : "";
  const count = typeof items === "number" ? `${formatInteger(items)} items` : "";
  return [count, size, typeof model === "string" ? model : ""].filter(Boolean).join(" | ") || "n/a";
}

function queueTime(value?: number | null) {
  return value == null ? "n/a" : `${formatNumber(value)}s`;
}

function queueTimestamp(item: LocalGpuQueueItem) {
  const value = item.finishedAt || item.startedAt || item.createdAt;
  return value ? new Date(value).toLocaleString() : "n/a";
}

function adaptiveSlotInfo(queue: LocalGpuQueueStatus, resourceClass: string, configuredSlots?: number) {
  const adaptive = queue.adaptiveSlots?.[resourceClass];
  return {
    admittedSlots: adaptive?.activeSlots ?? configuredSlots,
    configuredSlots: adaptive?.maxSlots ?? configuredSlots,
    reason: adaptive?.reason,
    pressure: adaptive?.pressure,
  };
}

function adaptiveDetail(queue: LocalGpuQueueStatus, resourceClass: string, configuredSlots?: number) {
  const adaptive = adaptiveSlotInfo(queue, resourceClass, configuredSlots);
  const pressure = adaptive.pressure;
  const pressureText = pressure?.available
    ? `GPU ${formatNumber(pressure.gpuPercent)}%, VRAM ${formatNumber(pressure.memoryUsedPercent)}%, ${formatNumber(pressure.temperatureC)} C`
    : "no pressure sample";
  return `${adaptive.reason || "fixed admission"} | admitted ${formatInteger(adaptive.admittedSlots)} of ${formatInteger(adaptive.configuredSlots)} | ${pressureText}`;
}

function resourceRows(queue: LocalGpuQueueStatus) {
  const byResource = queue.byResource || {};
  const configured = [
    ["local_llm", queue.llmSlots],
    ["cuda_batch", queue.cudaSlots],
    ["ocr_cuda", queue.ocrSlots],
  ] as const;
  const extras = Object.keys(byResource)
    .filter((key) => !configured.some(([configuredKey]) => configuredKey === key))
    .map((key) => [key, undefined] as const);
  return [...configured, ...extras].map(([resourceClass, slots]) => ({
    resourceClass,
    slots,
    adaptive: adaptiveSlotInfo(queue, resourceClass, slots),
    counts: byResource[resourceClass] || {},
  }));
}

export function LocalGpuQueuePanel({ queue }: { queue?: LocalGpuQueueStatus | null }) {
  if (!queue?.enabled) {
    return <div className="empty-state compact">Local GPU queue is not available.</div>;
  }

  return (
    <div className="local-gpu-queue-panel">
      <div className="status-grid">
        <div className="status-stat">
          <span>Detected GPUs</span>
          <strong>{formatInteger(queue.detectedGpus)}</strong>
        </div>
        <div className="status-stat">
          <span>LLM slots</span>
          <strong>{formatInteger(queue.llmSlots)}</strong>
        </div>
        <div className="status-stat">
          <span>CUDA slots</span>
          <strong>{formatInteger(queue.cudaSlots)}</strong>
        </div>
        <div className="status-stat">
          <span>OCR lanes</span>
          <strong title={adaptiveDetail(queue, "ocr_cuda", queue.ocrSlots)}>
            {formatInteger(queue.adaptiveSlots?.ocr_cuda?.activeSlots ?? queue.ocrSlots)} / {formatInteger(queue.ocrSlots)}
          </strong>
        </div>
        <div className="status-stat">
          <span>Active</span>
          <strong>{formatInteger(queue.active)}</strong>
        </div>
        <div className="status-stat">
          <span>Queued</span>
          <strong>{formatInteger(queue.queued)}</strong>
        </div>
        <div className="status-stat">
          <span>Oldest wait</span>
          <strong>{queueTime(queue.wait?.currentMaxWaitSeconds)}</strong>
        </div>
        <div className="status-stat">
          <span>Recent avg wait</span>
          <strong>{queueTime(queue.wait?.recentAvgWaitSeconds)}</strong>
        </div>
        <div className="status-stat">
          <span>Completed</span>
          <strong>{formatInteger(queue.completed)}</strong>
        </div>
        <div className="status-stat">
          <span>Timeout</span>
          <strong>{formatNumber(queue.queueTimeoutSeconds)}s</strong>
        </div>
      </div>

      <div className="gpu-queue-lanes">
        {resourceRows(queue).map((row) => (
          <div className="gpu-queue-lane-card" key={row.resourceClass}>
            <div>
              <span>{resourceLabel(row.resourceClass)}</span>
              <strong>{formatInteger(row.counts.running)} running</strong>
            </div>
            <div className="gpu-queue-lane-metrics">
              <span title={adaptiveDetail(queue, row.resourceClass, row.slots)}>
                <small>Admitted</small>
                {row.adaptive.admittedSlots == null ? "n/a" : `${formatInteger(row.adaptive.admittedSlots)} / ${formatInteger(row.adaptive.configuredSlots)}`}
              </span>
              <span><small>Queued</small>{formatInteger(row.counts.queued)}</span>
              <span><small>Done</small>{formatInteger(row.counts.completed)}</span>
              <span><small>Failed</small>{formatInteger(row.counts.failed)}</span>
            </div>
          </div>
        ))}
      </div>

      {queue.recent?.length ? (
        <div className="compact-table local-gpu-queue-table">
          <div className="compact-table-row compact-table-head">
            <span>When</span>
            <span>Work</span>
            <span>Lane</span>
            <span>Status</span>
            <span>Slot</span>
            <span>Wait</span>
            <span>Duration</span>
            <span>Detail</span>
          </div>
          {queue.recent.slice(0, 14).map((item) => (
            <div className={`compact-table-row gpu-queue-row ${item.status}`} key={item.taskId}>
              <span>{queueTimestamp(item)}</span>
              <span title={item.taskId}>{queueItemLabel(item)}</span>
              <span>{resourceLabel(item.resourceClass)}</span>
              <span>{item.status}</span>
              <span>{item.slotIndex == null ? "n/a" : String(item.slotIndex + 1)}</span>
              <span>{queueTime(item.waitSeconds)}</span>
              <span>{queueTime(item.durationSeconds)}</span>
              <span title={queueDetail(item)}>{queueDetail(item)}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state compact">No local GPU work recorded in the current window.</div>
      )}
    </div>
  );
}
