import type { LocalGpuQueueStatus } from "../../types/status";
import { formatInteger, formatNumber } from "../../libs/format";

function seconds(value?: number | null) {
  return value == null ? "n/a" : `${formatNumber(value)}s`;
}

function resourceCounts(queue: LocalGpuQueueStatus | null | undefined, resource: string) {
  return queue?.byResource?.[resource] ?? {};
}

function QueueLane({
  label,
  running,
  slots,
  queued,
  wait
}: {
  label: string;
  running?: number | null;
  slots?: number | null;
  queued?: number | null;
  wait?: number | null;
}) {
  return (
    <span className="ingest-gpu-queue-lane">
      <small>{label}</small>
      <strong>{formatInteger(running)} / {formatInteger(slots)}</strong>
      <em>{formatInteger(queued)} queued · wait {seconds(wait)}</em>
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
      <QueueLane label="OCR lanes" running={ocr.running} slots={queue.ocrSlots} queued={ocr.queued} wait={wait} />
      <QueueLane label="CUDA lanes" running={cuda.running} slots={queue.cudaSlots} queued={cuda.queued} wait={wait} />
      <QueueLane label="LLM lane" running={llm.running} slots={queue.llmSlots} queued={llm.queued} wait={wait} />
    </div>
  );
}
