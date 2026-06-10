import type { LocalGpuQueueStatus } from "../../types/status";
import { formatInteger, formatNumber } from "../../libs/format";

function seconds(value?: number | null) {
  return value == null ? "n/a" : `${formatNumber(value)}s`;
}

function resourceCounts(queue: LocalGpuQueueStatus | null | undefined, resource: string) {
  return queue?.byResource?.[resource] ?? {};
}

function adaptiveSlots(queue: LocalGpuQueueStatus | null | undefined, resource: string, fallback?: number | null) {
  return queue?.adaptiveSlots?.[resource]?.activeSlots ?? fallback;
}

function laneTitle(queue: LocalGpuQueueStatus | null | undefined, resource: string) {
  const adaptive = queue?.adaptiveSlots?.[resource];
  if (!adaptive) {
    return undefined;
  }
  const pressure = adaptive.pressure;
  const pressureText = pressure?.available
    ? `GPU ${formatNumber(pressure.gpuPercent)}%, VRAM ${formatNumber(pressure.memoryUsedPercent)}%, ${formatNumber(pressure.temperatureC)} C`
    : "GPU telemetry unavailable";
  return `${adaptive.reason || "adaptive admission"} | admitted ${formatInteger(adaptive.activeSlots)} of ${formatInteger(adaptive.maxSlots)} | ${pressureText}`;
}

function QueueLane({
  label,
  running,
  slots,
  maxSlots,
  queued,
  wait,
  title
}: {
  label: string;
  running?: number | null;
  slots?: number | null;
  maxSlots?: number | null;
  queued?: number | null;
  wait?: number | null;
  title?: string;
}) {
  return (
    <span className="ingest-gpu-queue-lane" title={title}>
      <small>{label}</small>
      <strong>{formatInteger(running)} / {formatInteger(slots)}</strong>
      <em>{formatInteger(queued)} queued · max {formatInteger(maxSlots ?? slots)} · wait {seconds(wait)}</em>
    </span>
  );
}

export function IngestGpuQueueSummary({ queue }: { queue?: LocalGpuQueueStatus | null }) {
  if (!queue?.enabled) {
    return null;
  }

  const ocr = resourceCounts(queue, "ocr_cuda");
  const cuda = resourceCounts(queue, "cuda_batch");
  const llm = resourceCounts(queue, "local_llm");
  const wait = queue.wait?.currentMaxWaitSeconds;

  return (
    <div className="ingest-gpu-queue-summary" title="Queue lanes show work currently admitted to local GPU resources. File phases can show OCR stage while individual image OCR jobs wait here.">
      <QueueLane
        label="OCR lanes"
        running={ocr.running}
        slots={adaptiveSlots(queue, "ocr_cuda", queue.ocrSlots)}
        maxSlots={queue.ocrSlots}
        queued={ocr.queued}
        wait={wait}
        title={laneTitle(queue, "ocr_cuda")}
      />
      <QueueLane label="CUDA lanes" running={cuda.running} slots={queue.cudaSlots} queued={cuda.queued} wait={wait} />
      <QueueLane label="LLM lane" running={llm.running} slots={queue.llmSlots} queued={llm.queued} wait={wait} />
    </div>
  );
}
