import type { DatasheetIntelligence, ReviewChunk, ReviewDocument, ReviewImage, ReviewScopeAudit } from "../types";
import { formatInteger } from "../libs/format";
import { maxChunkPreviewLimit } from "../hooks/useReviewQueue";
import { DatasheetIntelligencePanel } from "./DatasheetIntelligencePanel";
import { LoadingSpinner } from "./LoadingSpinner";
import { ReviewActions } from "./review/ReviewActions";
import { ReviewChunkList } from "./review/ReviewChunkList";
import { ReviewImageSection } from "./review/ReviewImageSection";
import { ReviewScopeAuditSection } from "./review/ReviewScopeAuditSection";
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
  images,
  intelligence,
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
  images: ReviewImage[];
  intelligence: DatasheetIntelligence | null;
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
      <div className="review-summary-strip">
        <span>
          Showing {formatInteger(chunks.length)} of {formatInteger(totalChunkCount)} parsed text chunks
        </span>
        <span>{formatInteger(images.length)} stored images</span>
        {canLoadMoreChunks ? (
          <button
            className="ghost-button compact-button"
            type="button"
            onClick={() => setChunkLimit(Math.min(chunkLimit + 100, chunkPreviewCap))}
            disabled={detailBusy}
          >
            Load more chunks
          </button>
        ) : null}
        {selectedDocument && totalChunkCount > maxChunkPreviewLimit && chunks.length >= maxChunkPreviewLimit ? (
          <span>Preview capped at {formatInteger(maxChunkPreviewLimit)} chunks</span>
        ) : null}
      </div>
      {detailBusy ? (
        <div className="review-loading">
          <LoadingSpinner />
          <span>Loading review details...</span>
        </div>
      ) : null}
      {!detailBusy ? <DatasheetIntelligencePanel intelligence={intelligence} /> : null}
      <ReviewImageSection images={images} selectedDocument={selectedDocument} detailBusy={detailBusy} />
      <ReviewScopeAuditSection rows={scopeAudit} />
      <ReviewChunkList chunks={chunks} detailBusy={detailBusy} />
    </div>
  );
}
