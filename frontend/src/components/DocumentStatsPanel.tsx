import type { DocumentDetail, DocumentSummary } from "../types";
import { formatInteger, formatNumber } from "../libs/format";

function uniquePageCount(detail: DocumentDetail): number {
  return new Set(detail.pages.map((page) => String(page.page))).size;
}

function countFromDetail(detail: DocumentDetail): { chunks: number; images: number; pages: number } {
  return {
    chunks: detail.ingestStats?.chunkCount ?? detail.chunks.length,
    images: detail.ingestStats?.storedImageCount ?? detail.images.length,
    pages: uniquePageCount(detail)
  };
}

export function DocumentStatsPanel({
  detail,
  summary
}: {
  detail: DocumentDetail | null;
  summary?: DocumentSummary | null;
}) {
  if (!detail) {
    return <div className="empty-state compact">Select a document to inspect its catalog statistics.</div>;
  }

  const factCount = detail.intelligence?.facts.length ?? 0;
  const pinCount = detail.pinout.pins.length;
  const stats = detail.ingestStats;
  const detailCounts = countFromDetail(detail);
  const catalogChunks = summary?.chunkCount ?? detailCounts.chunks;
  const catalogImages = summary?.imageCount ?? detailCounts.images;
  const catalogPages = detailCounts.pages;

  return (
    <div className="document-stats-panel">
      <div className="document-stat-grid">
        <div className="document-stat">
          <span>Pages</span>
          <strong>{formatInteger(catalogPages)}</strong>
          <small>with indexed content</small>
        </div>
        <div className="document-stat">
          <span>Chunks</span>
          <strong>{formatInteger(catalogChunks)}</strong>
          <small>{formatInteger(detail.chunks.length)} loaded here</small>
        </div>
        <div className="document-stat">
          <span>Image assets</span>
          <strong>{formatInteger(catalogImages)}</strong>
          <small>{formatInteger(detail.images.length)} loaded here</small>
        </div>
        <div className="document-stat">
          <span>Detected pins</span>
          <strong>{formatInteger(pinCount)}</strong>
          <small>{pinCount ? "from datasheet intelligence" : "none detected"}</small>
        </div>
        <div className="document-stat">
          <span>Facts</span>
          <strong>{formatInteger(factCount)}</strong>
          <small>{factCount ? "extracted facts" : "none detected"}</small>
        </div>
      </div>

      {stats ? (
        <div className="document-ingest-stats">
          <span>Raw chunks: {formatInteger(stats.rawChunkCount)}</span>
          <span>Dropped chunks: {formatInteger(stats.droppedChunkCount)}</span>
          <span>Extracted images: {formatInteger(stats.extractedImageCount)}</span>
          <span>Stored images: {formatInteger(stats.storedImageCount)}</span>
          <span>Indexed image OCR: {formatInteger(stats.indexedImageTextCount)}</span>
        </div>
      ) : null}

      {detail.intelligence ? (
        <div className="document-detection-summary">
          <strong>{detail.intelligence.componentName || detail.intelligence.displayName}</strong>
          <span>
            {detail.intelligence.componentType} | Confidence {formatNumber(detail.intelligence.confidence)}
          </span>
          {detail.intelligence.summary ? <p>{detail.intelligence.summary}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
