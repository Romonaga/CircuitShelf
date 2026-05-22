import type { DocumentDetail } from "../types";
import { formatInteger, formatNumber } from "../lib/format";

function uniquePageCount(detail: DocumentDetail): number {
  return new Set(detail.pages.map((page) => String(page.page))).size;
}

export function DocumentStatsPanel({ detail }: { detail: DocumentDetail | null }) {
  if (!detail) {
    return <div className="empty-state compact">Select a document to inspect its catalog statistics.</div>;
  }

  const factCount = detail.intelligence?.facts.length ?? 0;
  const pinCount = detail.pinout.pins.length;

  return (
    <div className="document-stats-panel">
      <div className="document-stat-grid">
        <div className="document-stat">
          <span>Pages</span>
          <strong>{formatInteger(uniquePageCount(detail))}</strong>
        </div>
        <div className="document-stat">
          <span>Chunks</span>
          <strong>{formatInteger(detail.chunks.length)}</strong>
        </div>
        <div className="document-stat">
          <span>Image assets</span>
          <strong>{formatInteger(detail.images.length)}</strong>
        </div>
        <div className="document-stat">
          <span>Detected pins</span>
          <strong>{formatInteger(pinCount)}</strong>
        </div>
        <div className="document-stat">
          <span>Facts</span>
          <strong>{formatInteger(factCount)}</strong>
        </div>
      </div>

      {detail.intelligence ? (
        <div className="document-detection-summary">
          <strong>{detail.intelligence.componentName || detail.intelligence.displayName}</strong>
          <span>
            {detail.intelligence.componentType} | Confidence {formatNumber(detail.intelligence.confidence)}
          </span>
          {detail.intelligence.summary ? <p>{detail.intelligence.summary}</p> : null}
        </div>
      ) : null}

      {pinCount ? (
        <details className="document-pinout-details">
          <summary>Detected pinout ({formatInteger(pinCount)})</summary>
          <div className="document-pinout-grid">
            {detail.pinout.pins.map((pin) => (
              <div key={pin.pin} className="document-pin-card">
                <span>Pin {pin.pin}</span>
                <strong>{pin.function}</strong>
                {pin.page ? <small>Page {pin.page}</small> : null}
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}
