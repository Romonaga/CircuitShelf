import type { DocumentDetail, DocumentPage, DocumentSummary, StatusPayload } from "../../types";
import { formatInteger } from "../../libs/format";
import { DatasheetIntelligencePanel } from "../DatasheetIntelligencePanel";
import { DocumentPageInspector } from "../DocumentPageInspector";
import { DocumentStatsPanel } from "../DocumentStatsPanel";
import { IngestStatusPanel } from "../IngestStatusPanel";
import { LoadingSpinner } from "../LoadingSpinner";
import { SectionHeader } from "../SectionHeader";

export function DocumentDetailPanel({
  detail,
  detailBusy,
  emptyText,
  isAdmin,
  selectedDocument,
  selectedPage,
  status,
  onOpenReview,
  onSelectPage
}: {
  detail: DocumentDetail | null;
  detailBusy: boolean;
  emptyText: string;
  isAdmin: boolean;
  selectedDocument: DocumentSummary | null;
  selectedPage: DocumentPage | null;
  status: StatusPayload | null;
  onOpenReview: () => void;
  onSelectPage: (page: number | string) => void;
}) {
  const displayedChunkCount = selectedDocument?.chunkCount ?? detail?.ingestStats?.chunkCount ?? detail?.chunks.length ?? 0;
  const displayedImageCount = selectedDocument?.imageCount ?? detail?.ingestStats?.storedImageCount ?? detail?.images.length ?? 0;

  return (
    <div className="chunk-panel document-detail-panel">
      {isAdmin ? (
        <IngestStatusPanel
          ingest={status?.ingest}
          workerBudget={status?.ingestWorkerBudget}
          runtimeBatches={status?.runtimeBatches}
          pendingReview={status?.pendingReview}
          onOpenReview={onOpenReview}
        />
      ) : null}
      <SectionHeader
        title={selectedDocument?.displayName ?? selectedDocument?.source ?? "No document selected"}
        description={
          detailBusy
            ? "Loading document details..."
            : `${formatInteger(displayedChunkCount)} chunks | ${formatInteger(displayedImageCount)} images`
        }
      />
      {detailBusy ? (
        <div className="document-loading">
          <LoadingSpinner />
          <span>Loading document details...</span>
        </div>
      ) : null}
      {!detailBusy ? <DocumentStatsPanel detail={detail} summary={selectedDocument} /> : null}
      {!detailBusy ? <DatasheetIntelligencePanel intelligence={detail?.intelligence} /> : null}
      {!detailBusy && detail?.pages.length ? (
        <div className="document-explorer">
          <div className="page-strip">
            {detail.pages.map((page) => (
              <button
                key={page.page}
                className={String(page.page) === String(selectedPage?.page) ? "page-chip active" : "page-chip"}
                onClick={() => onSelectPage(page.page)}
              >
                Page {page.page}
                <small>{formatInteger(page.chunks.length)} chunks | {formatInteger(page.images.length)} images</small>
              </button>
            ))}
          </div>
          <div className="page-detail">
            {selectedPage ? <DocumentPageInspector page={selectedPage} /> : null}
          </div>
        </div>
      ) : !detailBusy ? (
        <div className="empty-state">{emptyText}</div>
      ) : null}
    </div>
  );
}
