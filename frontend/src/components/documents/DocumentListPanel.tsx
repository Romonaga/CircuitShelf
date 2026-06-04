import { type MouseEvent, type ReactNode } from "react";
import type { DocumentSummary } from "../../types";
import { formatInteger } from "../../libs/format";
import { ErrorMessage } from "../ErrorMessage";
import { LoadingSpinner } from "../LoadingSpinner";
import { SectionHeader } from "../SectionHeader";

export function DocumentListPanel({
  title,
  description,
  busy,
  detailBusy,
  documents,
  filter,
  selected,
  error,
  message,
  actions,
  uploadPanel,
  onFilterChange,
  onSelect,
  onContextMenu
}: {
  title: string;
  description: string;
  busy: boolean;
  detailBusy: boolean;
  documents: DocumentSummary[];
  filter: string;
  selected: string;
  error: string;
  message: string;
  actions?: ReactNode;
  uploadPanel?: ReactNode;
  onFilterChange: (value: string) => void;
  onSelect: (source: string) => void;
  onContextMenu: (event: MouseEvent, document: DocumentSummary) => void;
}) {
  return (
    <div className="document-list-panel">
      <SectionHeader title={title} description={busy ? "Loading..." : description} actions={actions} />
      {uploadPanel}
      <input value={filter} onChange={(event) => onFilterChange(event.target.value)} placeholder="Filter documents" />
      {message ? <p className="success-message">{message}</p> : null}
      <ErrorMessage message={error} />
      <div className="document-list">
        {documents.map((document) => (
          <button
            key={document.source}
            className={document.source === selected ? "document-row active" : "document-row"}
            onClick={() => onSelect(document.source)}
            onContextMenu={(event) => onContextMenu(event, document)}
          >
            <span className="document-row-title">
              {document.displayName ?? document.source}
              {detailBusy && document.source === selected ? <LoadingSpinner className="document-row-spinner" /> : null}
            </span>
            <small>
              {formatInteger(document.chunkCount)} chunks | {formatInteger(document.imageCount)} images
            </small>
          </button>
        ))}
      </div>
    </div>
  );
}
