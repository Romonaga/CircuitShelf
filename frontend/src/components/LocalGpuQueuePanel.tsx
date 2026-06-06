import type { LocalGpuQueueStatus } from "../types/status";
import { formatInteger, formatNumber } from "../libs/format";

function queueItemLabel(item: NonNullable<LocalGpuQueueStatus["recent"]>[number]) {
  const owner = item.owner ? `${item.owner} · ` : "";
  return `${owner}${item.taskType}`;
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
          <span>Queue slots</span>
          <strong>{formatInteger(queue.slots)}</strong>
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
          <span>Completed</span>
          <strong>{formatInteger(queue.completed)}</strong>
        </div>
        <div className="status-stat">
          <span>Timeout</span>
          <strong>{formatNumber(queue.queueTimeoutSeconds)}s</strong>
        </div>
      </div>
      {queue.recent?.length ? (
        <div className="compact-table local-gpu-queue-table">
          <div className="compact-table-row compact-table-head">
            <span>Work</span>
            <span>Status</span>
            <span>Slot</span>
            <span>Wait</span>
            <span>Duration</span>
          </div>
          {queue.recent.slice(0, 8).map((item) => (
            <div className="compact-table-row" key={item.taskId}>
              <span title={item.taskId}>{queueItemLabel(item)}</span>
              <span>{item.status}</span>
              <span>{item.slotIndex == null ? "n/a" : String(item.slotIndex + 1)}</span>
              <span>{item.waitSeconds == null ? "n/a" : `${formatNumber(item.waitSeconds)}s`}</span>
              <span>{item.durationSeconds == null ? "n/a" : `${formatNumber(item.durationSeconds)}s`}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state compact">No local GPU work recorded in the current window.</div>
      )}
    </div>
  );
}
