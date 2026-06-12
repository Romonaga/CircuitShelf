import { useState } from "react";
import type { DocumentDetail, DocumentPage, DocumentSummary, StatusPayload } from "../../types";
import { formatInteger } from "../../libs/format";
import { downloadDocumentSource } from "../../libs/api";
import { downloadBlob } from "../../libs/download";
import { errorMessage } from "../../libs/errors";
import { CodeSamplePanel } from "../CodeSamplePanel";
import { DatasheetIntelligencePanel } from "../DatasheetIntelligencePanel";
import { ErrorMessage } from "../ErrorMessage";
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
  showEmptyInspector = true,
  scope,
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
  showEmptyInspector?: boolean;
  scope: "visible" | "global";
  status: StatusPayload | null;
  onOpenReview: () => void;
  onSelectPage: (page: number | string) => void;
}) {
  const [downloadBusy, setDownloadBusy] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const displayedChunkCount = selectedDocument?.chunkCount ?? detail?.ingestStats?.chunkCount ?? detail?.chunks.length ?? 0;
  const displayedImageCount = selectedDocument?.imageCount ?? detail?.ingestStats?.storedImageCount ?? detail?.images.length ?? 0;
  const showInspector = Boolean(selectedDocument || detailBusy || showEmptyInspector);

  async function downloadSource() {
    if (!selectedDocument?.source) {
      return;
    }
    setDownloadBusy(true);
    setDownloadError("");
    try {
      const blob = await downloadDocumentSource(selectedDocument.source, scope);
      downloadBlob(blob, selectedDocument.displayName || selectedDocument.source);
    } catch (err) {
      setDownloadError(errorMessage(err, "Could not download source document"));
    } finally {
      setDownloadBusy(false);
    }
  }

  return (
    <div className="chunk-panel document-detail-panel">
      {isAdmin ? (
        <IngestStatusPanel
          display="expanded"
          ingest={status?.ingest}
          workerBudget={status?.ingestWorkerBudget}
          runtimeBatches={status?.runtimeBatches}
          localGpuQueue={status?.localGpuQueue}
          pendingReview={status?.pendingReview}
          onOpenReview={onOpenReview}
        />
      ) : null}
      {showInspector ? (
        <>
          <SectionHeader
            title={selectedDocument?.displayName ?? selectedDocument?.source ?? "No document selected"}
            description={
              detailBusy
                ? "Loading document details..."
                : `${formatInteger(displayedChunkCount)} chunks | ${formatInteger(displayedImageCount)} images`
            }
            actions={
              selectedDocument ? (
                <button className="ghost-button" type="button" onClick={() => void downloadSource()} disabled={downloadBusy || detailBusy}>
                  {downloadBusy ? "Preparing..." : "Download source"}
                </button>
              ) : null
            }
          />
          <ErrorMessage message={downloadError} />
          {detailBusy ? (
            <div className="document-loading">
              <LoadingSpinner />
              <span>Loading document details...</span>
            </div>
          ) : null}
          {!detailBusy ? <DocumentStatsPanel detail={detail} summary={selectedDocument} /> : null}
          {!detailBusy ? <DatasheetIntelligencePanel intelligence={detail?.intelligence} /> : null}
          {!detailBusy ? <CodeSamplePanel codeSample={detail?.codeSample} /> : null}
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
        </>
      ) : null}
    </div>
  );
}
