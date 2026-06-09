import { type MouseEvent, useState } from "react";
import { DocumentContextMenu, type DocumentContextMenuState, type DocumentMenuItem } from "./DocumentContextMenu";
import { ReviewDocumentDetail } from "./ReviewDocumentDetail";
import { ReviewDocumentList } from "./ReviewDocumentList";
import { initialChunkPreviewLimit, useReviewQueue } from "../hooks/useReviewQueue";
import type { ReviewDocument } from "../types";

export function ReviewView({
  canManageSystem,
  isActive,
  refreshSignal,
  onStatusChange
}: {
  canManageSystem: boolean;
  isActive: boolean;
  refreshSignal: number;
  onStatusChange: () => void;
}) {
  const review = useReviewQueue({ isActive, refreshSignal, onStatusChange });
  const [contextMenu, setContextMenu] = useState<DocumentContextMenuState | null>(null);

  function selectReviewDocument(document: ReviewDocument) {
    review.setChunkLimit(initialChunkPreviewLimit);
    review.setSelected(document.source);
  }

  function openDocumentContextMenu(event: MouseEvent, document: ReviewDocument) {
    event.preventDefault();
    selectReviewDocument(document);
    setContextMenu({ document, x: event.clientX, y: event.clientY });
  }

  async function reindexDocument(document: DocumentMenuItem) {
    await review.reindexDocument(document);
    setContextMenu(null);
  }

  async function removeDocument(document: DocumentMenuItem) {
    const displayName = document.displayName ?? document.source;
    const confirmed = window.confirm(`Remove ${displayName} from CircuitShelf?\n\nThis removes the pending review document and deletes the source file from the training folder.`);
    if (!confirmed) {
      setContextMenu(null);
      return;
    }
    await review.removeDocument(document);
    setContextMenu(null);
  }

  async function reindexSelectedDocument() {
    if (!review.selectedDocument && review.selectedDocuments.length === 0) {
      return;
    }
    await review.reindexSelectedDocuments();
  }

  async function downloadSelectedDocument() {
    if (!review.selectedDocument) {
      return;
    }
    await review.downloadDocument(review.selectedDocument);
  }

  async function removeSelectedDocument() {
    const selectedDocument = review.selectedDocument;
    if (!selectedDocument && review.selectedDocuments.length === 0) {
      return;
    }
    if (review.selectedDocuments.length > 0) {
      const confirmed = window.confirm(`Remove ${review.selectedDocuments.length} selected documents from CircuitShelf?\n\nThis removes the pending review documents and deletes their source files from the training folder.`);
      if (!confirmed) {
        return;
      }
      await review.removeSelectedDocuments();
      return;
    }
    if (selectedDocument) {
      await removeDocument(selectedDocument);
    }
  }

  return (
    <section className="view-grid review-grid">
      <ReviewDocumentList
        actionBusy={review.actionBusy}
        busy={review.busy}
        documents={review.filteredDocuments}
        error={review.error}
        filter={review.filter}
        message={review.message}
        onContextMenu={openDocumentContextMenu}
        onClearSelection={review.clearSelection}
        onFilterChange={review.setFilter}
        onRefresh={review.loadDocuments}
        onSelect={selectReviewDocument}
        onSelectAll={review.selectAllFiltered}
        onToggleSelection={review.toggleSelection}
        selected={review.selected}
        selectedSources={review.selectedSources}
      />
      <ReviewDocumentDetail
        actionBusy={review.actionBusy}
        approveSelected={review.approveSelected}
        canLoadMoreChunks={review.canLoadMoreChunks}
        canManageSystem={canManageSystem}
        changeSelectedScope={review.changeSelectedScope}
        chunkLimit={review.chunkLimit}
        chunkPreviewCap={review.chunkPreviewCap}
        chunks={review.chunks}
        detailBusy={review.detailBusy}
        downloadSelected={() => void downloadSelectedDocument()}
        images={review.images}
        intelligence={review.intelligence}
        reindexSelected={() => void reindexSelectedDocument()}
        removeSelected={() => void removeSelectedDocument()}
        scopeAudit={review.scopeAudit}
        selectedCount={review.selectedDocuments.length}
        selectedDocument={review.selectedDocument}
        setChunkLimit={review.setChunkLimit}
        totalChunkCount={review.totalChunkCount}
      />
      <DocumentContextMenu
        menu={contextMenu}
        removing={review.actionBusy}
        reindexing={review.actionBusy}
        onClose={() => setContextMenu(null)}
        onReindex={(document) => void reindexDocument(document)}
        onRemove={(document) => void removeDocument(document)}
      />
    </section>
  );
}
