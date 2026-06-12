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
    selectedDocuments: documents.selectedDocuments,
    clearSelection: documents.clearSelection,
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
    allFilteredSelected: documents.allFilteredSelected,
    approveSelected: actions.approveSelected,
    busy: documents.busy,
    canLoadMoreChunks,
    changeSelectedScope: actions.changeSelectedScope,
    chunkLimit,
    chunkPreviewCap,
    chunks: detail.chunks,
    codeSample: detail.codeSample,
    detailBusy: detail.detailBusy,
    documents: documents.documents,
    downloadDocument: actions.downloadDocument,
    error: documents.error,
    filters: documents.filters,
    filteredDocuments: documents.filteredDocuments,
    folderOptions: documents.folderOptions,
    images: detail.images,
    intelligence: detail.intelligence,
    loadDocuments: documents.loadDocuments,
    message: actions.message,
    reindexDocument: actions.reindexDocument,
    reindexSelectedDocuments: actions.reindexSelectedDocuments,
    removeDocument: actions.removeDocument,
    removeSelectedDocuments: actions.removeSelectedDocuments,
    scopeAudit: detail.scopeAudit,
    selected: documents.selected,
    selectedDocument: documents.selectedDocument,
    selectedDocuments: documents.selectedDocuments,
    selectedSources: documents.selectedSources,
    setChunkLimit,
    clearSelection: documents.clearSelection,
    resetFilters: documents.resetFilters,
    setFolderFilter: documents.setFolderFilter,
    setHealthFilter: documents.setHealthFilter,
    setKindFilter: documents.setKindFilter,
    setSearchFilter: documents.setSearchFilter,
    setSelected,
    selectAllFiltered: documents.selectAllFiltered,
    toggleSelection: documents.toggleSelection,
    totalChunkCount
  };
}
