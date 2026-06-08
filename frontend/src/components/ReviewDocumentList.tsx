import type { MouseEvent } from "react";
import type { ReviewDocument } from "../types";
import { formatInteger } from "../libs/format";
import { ErrorMessage } from "./ErrorMessage";
import { ReviewScopeBadge } from "./ReviewScopeBadge";
import { SectionHeader } from "./SectionHeader";

export function ReviewDocumentList({
  actionBusy,
  busy,
  documents,
  error,
  filter,
  message,
  onContextMenu,
  onFilterChange,
  onRefresh,
  onSelect,
  selected
}: {
  actionBusy: boolean;
  busy: boolean;
  documents: ReviewDocument[];
  error: string;
  filter: string;
  message: string;
  onContextMenu: (event: MouseEvent, document: ReviewDocument) => void;
  onFilterChange: (value: string) => void;
  onRefresh: () => void;
  onSelect: (document: ReviewDocument) => void;
  selected: string;
}) {
  return (
    <div className="document-list-panel">
      <SectionHeader
        title="Review"
        description={busy ? "Loading..." : `${formatInteger(documents.length)} pending documents`}
        actions={
          <button className="ghost-button" type="button" onClick={onRefresh} disabled={busy || actionBusy}>
            {busy ? "Refreshing..." : "Refresh"}
          </button>
        }
      />
      <input value={filter} onChange={(event) => onFilterChange(event.target.value)} placeholder="Filter review queue" />
      <div className="review-list-feedback">
        {message ? <p className="success-message">{message}</p> : null}
        <ErrorMessage message={error} />
      </div>
      <div className="document-list">
        {documents.map((document) => (
          <button
            key={document.source}
            className={document.source === selected ? "document-row active" : "document-row"}
            onClick={() => onSelect(document)}
            onContextMenu={(event) => onContextMenu(event, document)}
          >
            <span>{document.displayName}</span>
            <small className="review-row-meta">
              <ReviewScopeBadge document={document} />
              <span>{document.status}</span>
              <span>{formatInteger(document.chunkCount)} chunks</span>
              <span>{formatInteger(document.imageCount)} images</span>
            </small>
          </button>
        ))}
        {!documents.length ? <div className="empty-state compact">No documents need review.</div> : null}
      </div>
    </div>
  );
}
