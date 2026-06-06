import type { IngestStatus } from "../../types";
import { formatInteger } from "../../libs/format";
import { formatDateTime, formatDetailLabel, formatDetailValue, formatStage } from "../../libs/ingest/format";

export function IngestDetailGrid({ ingest }: { ingest: IngestStatus }) {
  const totalFiles = ingest.totalFiles ?? 0;
  const processedFiles = ingest.processedFiles ?? 0;
  const details = Object.entries(ingest.details ?? {}).filter(([, value]) => value !== undefined);
  const items = [
    { label: "Stage", value: formatStage(ingest.stage) },
    ...(ingest.running && totalFiles ? [{ label: "Progress", value: `${formatInteger(processedFiles)} / ${formatInteger(totalFiles)} files` }] : []),
    ...details.map(([key, value]) => ({ label: formatDetailLabel(key), value: formatDetailValue(value) })),
    { label: "Started", value: formatDateTime(ingest.lastStartedAt) },
    { label: "Finished", value: formatDateTime(ingest.lastFinishedAt) },
    { label: "Result", value: ingest.lastResult || "waiting" },
    { label: "Next check", value: formatDateTime(ingest.nextCheckAt) }
  ];

  return (
    <div className="ingest-status-grid">
      {items.map((item) => (
        <span key={item.label} title={`${item.label}: ${item.value}`}>
          <small>{item.label}</small>
          <strong>{item.value}</strong>
        </span>
      ))}
    </div>
  );
}
