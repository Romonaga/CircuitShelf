import type { ReviewChunk, ReviewDocument, ReviewImage, ReviewScopeAudit } from "../../types";
import { formatInteger } from "../../libs/format";
import { maxChunkPreviewLimit } from "../../libs/review/reviewQueue";
import { ReviewChunkList } from "./ReviewChunkList";
import { ReviewImageSection } from "./ReviewImageSection";
import { ReviewScopeAuditSection } from "./ReviewScopeAuditSection";

export function ReviewDeepInspectPanel({
  canLoadMoreChunks,
  chunkLimit,
  chunkPreviewCap,
  chunks,
  detailBusy,
  images,
  scopeAudit,
  selectedDocument,
  setChunkLimit,
  totalChunkCount
}: {
  canLoadMoreChunks: boolean;
  chunkLimit: number;
  chunkPreviewCap: number;
  chunks: ReviewChunk[];
  detailBusy: boolean;
  images: ReviewImage[];
  scopeAudit: ReviewScopeAudit[];
  selectedDocument: ReviewDocument;
  setChunkLimit: (limit: number) => void;
  totalChunkCount: number;
}) {
  return (
    <details className="review-deep-inspect">
      <summary>
        <span>Deep inspect</span>
        <small>{formatInteger(totalChunkCount)} chunks | {formatInteger(images.length)} images | {formatInteger(scopeAudit.length)} audit rows</small>
      </summary>
      <div className="review-summary-strip">
        <span>Loaded {formatInteger(chunks.length)} of {formatInteger(totalChunkCount)} parsed text chunks</span>
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
        {totalChunkCount > maxChunkPreviewLimit && chunks.length >= maxChunkPreviewLimit ? (
          <span>Preview capped at {formatInteger(maxChunkPreviewLimit)} chunks</span>
        ) : null}
      </div>
      <ReviewImageSection images={images} selectedDocument={selectedDocument} detailBusy={detailBusy} defaultOpen={false} />
      <ReviewScopeAuditSection rows={scopeAudit} />
      <ReviewChunkList chunks={chunks} detailBusy={detailBusy} />
    </details>
  );
}
