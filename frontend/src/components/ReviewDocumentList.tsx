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
  onClearSelection,
  onFilterChange,
  onRefresh,
  onSelect,
  onSelectAll,
  onToggleSelection,
  selected,
  selectedSources
}: {
  actionBusy: boolean;
  busy: boolean;
  documents: ReviewDocument[];
  error: string;
  filter: string;
  message: string;
  onContextMenu: (event: MouseEvent, document: ReviewDocument) => void;
  onClearSelection: () => void;
  onFilterChange: (value: string) => void;
  onRefresh: () => void;
  onSelect: (document: ReviewDocument) => void;
  onSelectAll: () => void;
  onToggleSelection: (source: string) => void;
  selected: string;
  selectedSources: string[];
}) {
  const selectedSet = new Set(selectedSources);
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
      <div className="review-selection-toolbar">
        <span>{formatInteger(selectedSources.length)} selected</span>
        <button className="ghost-button compact-button" type="button" onClick={onSelectAll} disabled={busy || actionBusy || documents.length === 0}>
          Select visible
        </button>
        <button className="ghost-button compact-button" type="button" onClick={onClearSelection} disabled={busy || actionBusy || selectedSources.length === 0}>
          Clear
        </button>
      </div>
      <div className="review-list-feedback">
        {message ? <p className="success-message">{message}</p> : null}
        <ErrorMessage message={error} />
      </div>
      <div className="document-list">
        {documents.map((document) => (
          <div
            key={document.source}
            className={document.source === selected ? "review-row-shell active" : "review-row-shell"}
            onContextMenu={(event) => onContextMenu(event, document)}
          >
            <input
              aria-label={`Select ${document.displayName}`}
              checked={selectedSet.has(document.source)}
              className="review-row-checkbox"
              disabled={busy || actionBusy}
              type="checkbox"
              onChange={() => onToggleSelection(document.source)}
              onClick={(event) => event.stopPropagation()}
            />
            <button
              className="document-row"
              onClick={() => onSelect(document)}
            >
              <span>{document.displayName}</span>
              <small className="review-row-meta">
                <ReviewScopeBadge document={document} />
                <span>{document.status}</span>
                <span>{formatInteger(document.chunkCount)} chunks</span>
                <span>{formatInteger(document.imageCount)} images</span>
              </small>
            </button>
          </div>
        ))}
        {!documents.length ? <div className="empty-state compact">No documents need review.</div> : null}
      </div>
    </div>
  );
}
