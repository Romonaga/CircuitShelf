import type { MouseEvent } from "react";
import type { ReviewDocument } from "../types";
import { formatInteger } from "../libs/format";
import {
  defaultReviewTriageFilters,
  reviewDocumentFailed,
  reviewDocumentKindLabel,
  reviewDocumentLowQuality,
  type ReviewDocumentKindFilter,
  type ReviewHealthFilter,
  type ReviewTriageFilters
} from "../libs/review/reviewQueue";
import { ErrorMessage } from "./ErrorMessage";
import { ReviewScopeBadge } from "./ReviewScopeBadge";
import { SectionHeader } from "./SectionHeader";

const kindFilterLabels: { value: ReviewDocumentKindFilter; label: string }[] = [
  { value: "all", label: "All types" },
  { value: "pdf", label: "PDFs" },
  { value: "code", label: "Code" },
  { value: "text", label: "Text" },
  { value: "metadata", label: "Metadata" },
  { value: "other", label: "Other" }
];

const healthFilterLabels: { value: ReviewHealthFilter; label: string }[] = [
  { value: "all", label: "Any status" },
  { value: "ready", label: "Ready" },
  { value: "failed", label: "Failed" },
  { value: "no-chunks", label: "No chunks" },
  { value: "low-quality", label: "Low quality" },
  { value: "with-images", label: "With images" },
  { value: "without-images", label: "Without images" }
];

export function ReviewDocumentList({
  actionBusy,
  allCount,
  busy,
  documents,
  error,
  filters,
  folderOptions,
  message,
  onContextMenu,
  onClearSelection,
  onFolderFilterChange,
  onHealthFilterChange,
  onKindFilterChange,
  onRefresh,
  onResetFilters,
  onSelect,
  onSelectAll,
  onSearchFilterChange,
  onToggleSelection,
  selected,
  selectedSources
}: {
  actionBusy: boolean;
  allCount: number;
  busy: boolean;
  documents: ReviewDocument[];
  error: string;
  filters: ReviewTriageFilters;
  folderOptions: string[];
  message: string;
  onContextMenu: (event: MouseEvent, document: ReviewDocument) => void;
  onClearSelection: () => void;
  onFolderFilterChange: (value: string) => void;
  onHealthFilterChange: (value: ReviewHealthFilter) => void;
  onKindFilterChange: (value: ReviewDocumentKindFilter) => void;
  onRefresh: () => void;
  onResetFilters: () => void;
  onSelect: (document: ReviewDocument) => void;
  onSelectAll: () => void;
  onSearchFilterChange: (value: string) => void;
  onToggleSelection: (source: string) => void;
  selected: string;
  selectedSources: string[];
}) {
  const selectedSet = new Set(selectedSources);
  const hasActiveFilters =
    filters.search !== defaultReviewTriageFilters.search
    || filters.kind !== defaultReviewTriageFilters.kind
    || filters.health !== defaultReviewTriageFilters.health
    || filters.folder !== defaultReviewTriageFilters.folder;
  return (
    <div className="document-list-panel">
      <SectionHeader
        title="Review"
        description={
          busy
            ? "Loading..."
            : `${formatInteger(documents.length)} of ${formatInteger(allCount)} pending documents`
        }
        actions={
          <button className="ghost-button" type="button" onClick={onRefresh} disabled={busy || actionBusy}>
            {busy ? "Refreshing..." : "Refresh"}
          </button>
        }
      />
      <div className="review-filter-grid" aria-label="Review triage filters">
        <label>
          <span>Search</span>
          <input
            value={filters.search}
            onChange={(event) => onSearchFilterChange(event.target.value)}
            placeholder="Name, folder, status, scope"
          />
        </label>
        <label>
          <span>Type</span>
          <select
            value={filters.kind}
            onChange={(event) => onKindFilterChange(event.target.value as ReviewDocumentKindFilter)}
          >
            {kindFilterLabels.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Health</span>
          <select
            value={filters.health}
            onChange={(event) => onHealthFilterChange(event.target.value as ReviewHealthFilter)}
          >
            {healthFilterLabels.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Folder</span>
          <select value={filters.folder} onChange={(event) => onFolderFilterChange(event.target.value)}>
            <option value="all">All folders</option>
            {folderOptions.map((folder) => (
              <option key={folder} value={folder}>{folder}</option>
            ))}
          </select>
        </label>
        <button
          className="ghost-button compact-button review-filter-reset"
          type="button"
          onClick={onResetFilters}
          disabled={busy || actionBusy || !hasActiveFilters}
        >
          Reset
        </button>
      </div>
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
                <span>{reviewDocumentKindLabel(document)}</span>
                <span>{document.status}</span>
                <span>{formatInteger(document.chunkCount)} chunks</span>
                <span>{formatInteger(document.imageCount)} images</span>
                {reviewDocumentLowQuality(document) ? <span>{formatInteger(document.lowQualityCount)} low quality</span> : null}
                {reviewDocumentFailed(document) ? <span>Failed</span> : null}
              </small>
            </button>
          </div>
        ))}
        {!documents.length ? (
          <div className="empty-state compact">
            {allCount > 0 ? "No documents match the active filters." : "No documents need review."}
          </div>
        ) : null}
      </div>
    </div>
  );
}
