import type { DatasheetIntelligence, ReviewChunk, ReviewDocument, ReviewImage, ReviewScopeAudit } from "../types";
import { formatInteger } from "../libs/format";
import { DatasheetIntelligencePanel } from "./DatasheetIntelligencePanel";
import { LoadingSpinner } from "./LoadingSpinner";
import { ReviewActions } from "./review/ReviewActions";
import { ReviewDeepInspectPanel } from "./review/ReviewDeepInspectPanel";
import { ReviewEvidenceSamples } from "./review/ReviewEvidenceSamples";
import { ReviewQaSummary } from "./review/ReviewQaSummary";
import { ReviewScopeBadge } from "./ReviewScopeBadge";
import { SectionHeader } from "./SectionHeader";

export function ReviewDocumentDetail({
  actionBusy,
  approveSelected,
  canLoadMoreChunks,
  canManageSystem,
  changeSelectedScope,
  chunkLimit,
  chunkPreviewCap,
  chunks,
  detailBusy,
  downloadSelected,
  images,
  intelligence,
  reindexSelected,
  removeSelected,
  scopeAudit,
  selectedDocument,
  setChunkLimit,
  totalChunkCount
}: {
  actionBusy: boolean;
  approveSelected: (includeImages: boolean) => void;
  canLoadMoreChunks: boolean;
  canManageSystem: boolean;
  changeSelectedScope: (scope: "global" | "entity") => void;
  chunkLimit: number;
  chunkPreviewCap: number;
  chunks: ReviewChunk[];
  detailBusy: boolean;
  downloadSelected: () => void;
  images: ReviewImage[];
  intelligence: DatasheetIntelligence | null;
  reindexSelected: () => void;
  removeSelected: () => void;
  scopeAudit: ReviewScopeAudit[];
  selectedDocument: ReviewDocument | null;
  setChunkLimit: (limit: number) => void;
  totalChunkCount: number;
}) {
  return (
    <div className="chunk-panel review-panel">
      <SectionHeader
        title={selectedDocument?.displayName || "No document selected"}
        description={
          selectedDocument
            ? `Quality ${selectedDocument.avgQuality.toFixed(2)} | ${formatInteger(selectedDocument.lowQualityCount)} low-quality chunks`
            : "Review new or changed documents before retrieval."
        }
        actions={
          selectedDocument ? (
            <ReviewActions
              actionBusy={actionBusy}
              approveSelected={approveSelected}
              canManageSystem={canManageSystem}
              changeSelectedScope={changeSelectedScope}
              detailBusy={detailBusy}
              downloadSelected={downloadSelected}
              reindexSelected={reindexSelected}
              removeSelected={removeSelected}
              selectedDocument={selectedDocument}
            />
          ) : null
        }
      />
      {selectedDocument ? (
        <div className="review-scope-panel">
          <ReviewScopeBadge document={selectedDocument} />
          <span>{selectedDocument.isGlobal ? "Readable by every entity. Writable by system admins only." : "Readable by this entity plus system admins."}</span>
        </div>
      ) : null}
      {detailBusy ? (
        <div className="review-loading">
          <LoadingSpinner />
          <span>Loading review details...</span>
        </div>
      ) : null}
      {selectedDocument && !detailBusy ? (
        <>
          <ReviewQaSummary document={selectedDocument} chunks={chunks} images={images} intelligence={intelligence} />
          <DatasheetIntelligencePanel intelligence={intelligence} />
          <ReviewEvidenceSamples chunks={chunks} images={images} />
          <ReviewDeepInspectPanel
            canLoadMoreChunks={canLoadMoreChunks}
            chunkLimit={chunkLimit}
            chunkPreviewCap={chunkPreviewCap}
            chunks={chunks}
            detailBusy={detailBusy}
            images={images}
            scopeAudit={scopeAudit}
            selectedDocument={selectedDocument}
            setChunkLimit={setChunkLimit}
            totalChunkCount={totalChunkCount}
          />
        </>
      ) : null}
    </div>
  );
}
