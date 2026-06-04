import { useCallback, useEffect, useState } from "react";
import {
  initialChunkPreviewLimit,
  reviewChunkPreviewCap
} from "../libs/review/reviewQueue";
import { useReviewActions } from "./review/useReviewActions";
import { useReviewDocumentDetail } from "./review/useReviewDocumentDetail";
import { useReviewDocuments } from "./review/useReviewDocuments";

export { initialChunkPreviewLimit, maxChunkPreviewLimit } from "../libs/review/reviewQueue";

export function useReviewQueue({
  isActive,
  refreshSignal,
  onStatusChange
}: {
  isActive: boolean;
  refreshSignal: number;
  onStatusChange: () => void;
}) {
  const [chunkLimit, setChunkLimit] = useState(initialChunkPreviewLimit);
  const documents = useReviewDocuments();
  const detail = useReviewDocumentDetail({
    selected: documents.selected,
    chunkLimit,
    onError: documents.setError
  });
  const totalChunkCount = documents.selectedDocument?.chunkCount ?? detail.chunks.length;
  const chunkPreviewCap = reviewChunkPreviewCap(totalChunkCount);
  const canLoadMoreChunks = Boolean(
    documents.selectedDocument
      && detail.chunks.length < totalChunkCount
      && chunkLimit < chunkPreviewCap
  );
  const actions = useReviewActions({
    selectedDocument: documents.selectedDocument,
    clearDetails: detail.clearDetails,
    loadDocuments: documents.loadDocuments,
    onStatusChange,
    onScopeAuditChange: detail.setScopeAudit,
    setError: documents.setError
  });

  const setSelected = useCallback((source: string) => {
    setChunkLimit(initialChunkPreviewLimit);
    documents.setSelected(source);
  }, [documents.setSelected]);

  useEffect(() => {
    if (isActive) {
      void documents.loadDocuments();
    }
  }, [documents.loadDocuments, isActive, refreshSignal]);

  return {
    actionBusy: actions.actionBusy,
    approveSelected: actions.approveSelected,
    busy: documents.busy,
    canLoadMoreChunks,
    changeSelectedScope: actions.changeSelectedScope,
    chunkLimit,
    chunkPreviewCap,
    chunks: detail.chunks,
    detailBusy: detail.detailBusy,
    documents: documents.documents,
    error: documents.error,
    filter: documents.filter,
    filteredDocuments: documents.filteredDocuments,
    images: detail.images,
    intelligence: detail.intelligence,
    loadDocuments: documents.loadDocuments,
    message: actions.message,
    reindexSelected: actions.reindexSelected,
    removeSelected: actions.removeSelected,
    scopeAudit: detail.scopeAudit,
    selected: documents.selected,
    selectedDocument: documents.selectedDocument,
    setChunkLimit,
    setFilter: documents.setFilter,
    setSelected,
    totalChunkCount
  };
}
