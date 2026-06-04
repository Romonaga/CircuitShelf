import type { UploadProgress } from "../../api";
import { formatBytes, formatDurationMs, formatInteger } from "../../libs/format";
import { formatUploadEta, formatUploadEtaHeadline, formatUploadSpeed } from "../../libs/upload/progress";

export function UploadProgressPanel({ filesCount, progress }: { filesCount: number; progress: UploadProgress }) {
  const etaLabel = formatUploadEta(progress.etaSeconds, progress.percent);
  const elapsedMs = (progress.elapsedSeconds ?? 0) * 1000;

  return (
    <div className="upload-progress" role="status" aria-live="polite">
      <div className="upload-progress-headline">
        <span>
          <small>Estimated time left</small>
          <strong>{formatUploadEtaHeadline(progress.etaSeconds, progress.percent)}</strong>
        </span>
        <span>
          <small>Elapsed</small>
          <strong>{formatDurationMs(elapsedMs)}</strong>
        </span>
      </div>
      <div className="upload-progress-bar">
        <span style={{ width: `${progress.percent}%` }} />
      </div>
      <p>
        Uploading {formatInteger(filesCount)} file{filesCount === 1 ? "" : "s"} · {progress.percent}% · ETA {etaLabel} ·{" "}
        {formatBytes(progress.loaded)} / {progress.total > 0 ? formatBytes(progress.total) : "unknown size"}
      </p>
      <div className="upload-progress-stats">
        <span>
          <small>Speed</small>
          <strong>{formatUploadSpeed(progress.bytesPerSecond)}</strong>
        </span>
        <span>
          <small>ETA</small>
          <strong>{etaLabel}</strong>
        </span>
        <span>
          <small>Elapsed</small>
          <strong>{formatDurationMs(elapsedMs)}</strong>
        </span>
      </div>
    </div>
  );
}
