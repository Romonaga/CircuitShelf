import type { DatasheetIntelligence, ReviewChunk, ReviewDocument, ReviewImage, ReviewScopeAudit } from "../types";
import { formatInteger } from "../libs/format";
import { maxChunkPreviewLimit } from "../hooks/useReviewQueue";
import { DatasheetIntelligencePanel } from "./DatasheetIntelligencePanel";
import { LoadingSpinner } from "./LoadingSpinner";
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

function ReviewActions({
  actionBusy,
  approveSelected,
  canManageSystem,
  changeSelectedScope,
  detailBusy,
  reindexSelected,
  removeSelected,
  selectedDocument
}: {
  actionBusy: boolean;
  approveSelected: (includeImages: boolean) => void;
  canManageSystem: boolean;
  changeSelectedScope: (scope: "global" | "entity") => void;
  detailBusy: boolean;
  reindexSelected: () => void;
  removeSelected: () => void;
  selectedDocument: ReviewDocument;
}) {
  const disabled = actionBusy || detailBusy;
  return (
    <div className="review-actions">
      <button className="primary-button" onClick={() => approveSelected(true)} disabled={disabled}>
        Approve with images
      </button>
      {selectedDocument.imageCount > 0 ? (
        <button className="ghost-button" onClick={() => approveSelected(false)} disabled={disabled}>
          Approve text only
        </button>
      ) : null}
      {canManageSystem && !selectedDocument.isGlobal ? (
        <button className="ghost-button" onClick={() => changeSelectedScope("global")} disabled={disabled}>
          Promote to corpus
        </button>
      ) : null}
      {canManageSystem && selectedDocument.isGlobal ? (
        <button className="ghost-button" onClick={() => changeSelectedScope("entity")} disabled={disabled}>
          Make entity-private
        </button>
      ) : null}
      <button className="ghost-button" onClick={reindexSelected} disabled={disabled}>
        Re-index
      </button>
      <button className="ghost-button danger-button" onClick={removeSelected} disabled={disabled}>
        Remove
      </button>
    </div>
  );
}

function ReviewImageSection({
  detailBusy,
  images,
  selectedDocument
}: {
  detailBusy: boolean;
  images: ReviewImage[];
  selectedDocument: ReviewDocument | null;
}) {
  return (
    <details className="review-image-details">
      <summary>Image assets ({formatInteger(images.length)})</summary>
      <div className="review-images">
        {images.map((image) => (
          <article key={image.imageKey} className="review-image-card">
            <div className="chunk-meta">
              <strong>{image.caption}</strong>
              {image.page ? <span>Page {image.page}</span> : null}
              <span>{formatInteger(image.width)} x {formatInteger(image.height)}</span>
            </div>
            <img src={`data:${image.imageMimeType || "image/png"};base64,${image.imageBase64}`} alt={image.caption} />
          </article>
        ))}
        {selectedDocument && !detailBusy && !images.length ? <div className="empty-state compact">No image assets were extracted for this document.</div> : null}
      </div>
    </details>
  );
}

function ReviewScopeAuditSection({ rows }: { rows: ReviewScopeAudit[] }) {
  if (!rows.length) {
    return null;
  }
  return (
    <details className="review-scope-audit">
      <summary>Scope history ({formatInteger(rows.length)})</summary>
      <div className="review-scope-audit-list">
        {rows.map((row) => (
          <article key={row.id} className="review-scope-audit-row">
            <strong>{scopeName(row.newIsGlobal, row.newEntityName)}</strong>
            <span>from {scopeName(Boolean(row.previousIsGlobal), row.previousEntityName)}</span>
            <span>{row.changedByUsername || "system"}</span>
            <span>{row.createdAt ? new Date(row.createdAt).toLocaleString() : "unknown time"}</span>
            {row.reason ? <small>{row.reason}</small> : null}
          </article>
        ))}
      </div>
    </details>
  );
}

function ReviewChunkList({ chunks, detailBusy }: { chunks: ReviewChunk[]; detailBusy: boolean }) {
  return (
    <div className="chunk-table">
      {chunks.map((chunk) => (
        <article key={chunk.index} className={chunk.quality < 0.35 ? "chunk-row warning-row" : "chunk-row"}>
          <div className="chunk-meta">
            <strong>#{chunk.index}</strong>
            <span>{chunk.section}</span>
            <span>{chunk.category}</span>
            <span>{formatInteger(chunk.tokens)} tokens</span>
            <span>Quality {chunk.quality.toFixed(2)}</span>
            {chunk.page ? <span>Page {chunk.page}</span> : null}
            {chunk.sourceImageId ? <span>Image {chunk.sourceImageId}</span> : null}
            {chunk.isOcr ? <span>OCR</span> : null}
            {chunk.hasMath ? <span>Math</span> : null}
          </div>
          <p>{chunk.preview}</p>
          {chunk.qualityFlags.length ? <small>{chunk.qualityFlags.join(", ")}</small> : null}
        </article>
      ))}
      {!detailBusy && !chunks.length ? <div className="empty-state">Select a document to inspect review chunks.</div> : null}
    </div>
  );
}

function scopeName(isGlobal: boolean, entityName?: string) {
  return isGlobal ? "Global corpus" : `Entity: ${entityName || "Private"}`;
}
