import type { IngestStatus } from "../../types";
import { formatInteger } from "../../lib/format";
import { fileListSummary } from "../../lib/ingest/format";

export function IngestChangeSummary({ changes }: { changes: IngestStatus["lastChanges"] }) {
  if (!changes) {
    return null;
  }

  return (
    <>
      <div className="ingest-change-list">
        <span>Added {formatInteger(changes.added)}</span>
        <span>Modified {formatInteger(changes.modified)}</span>
        <span>Removed {formatInteger(changes.removed)}</span>
        <span>Unchanged {formatInteger(changes.unchanged)}</span>
      </div>
      {changes.unchangedFiles?.length ? (
        <p className="ingest-note">Skipped unchanged: {fileListSummary(changes.unchangedFiles)}</p>
      ) : null}
    </>
  );
}
