import { ReviewDocumentDetail } from "./ReviewDocumentDetail";
import { ReviewDocumentList } from "./ReviewDocumentList";
import { initialChunkPreviewLimit, useReviewQueue } from "../hooks/useReviewQueue";

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

  return (
    <section className="view-grid docs-grid">
      <ReviewDocumentList
        actionBusy={review.actionBusy}
        busy={review.busy}
        documents={review.filteredDocuments}
        error={review.error}
        filter={review.filter}
        message={review.message}
        onFilterChange={review.setFilter}
        onRefresh={review.loadDocuments}
        onSelect={(document) => {
          review.setChunkLimit(initialChunkPreviewLimit);
          review.setSelected(document.source);
        }}
        selected={review.selected}
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
        images={review.images}
        reindexSelected={review.reindexSelected}
        removeSelected={review.removeSelected}
        scopeAudit={review.scopeAudit}
        selectedDocument={review.selectedDocument}
        setChunkLimit={review.setChunkLimit}
        totalChunkCount={review.totalChunkCount}
      />
    </section>
  );
}
