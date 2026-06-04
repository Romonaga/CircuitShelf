import { formatInteger } from "../../lib/format";
import { formatReason } from "../../lib/ingest/format";
import { LoadingSpinner } from "../LoadingSpinner";

export function IngestStatusHeader({
  running,
  pendingReview,
  reason,
  onOpenReview
}: {
  running: boolean;
  pendingReview: number;
  reason?: string | null;
  onOpenReview?: () => void;
}) {
  return (
    <div className="ingest-status-heading">
      <div className="ingest-status-title">
        {running ? <LoadingSpinner className="ingest-spinner" /> : null}
        <strong>{running ? "Indexing documents..." : pendingReview ? "Documents ready for review" : "Indexing idle"}</strong>
        <p>{formatReason(reason)}</p>
      </div>
      {pendingReview && onOpenReview ? (
        <button className="ghost-button" type="button" onClick={onOpenReview}>
          Open Review ({formatInteger(pendingReview)})
        </button>
      ) : null}
    </div>
  );
}
