import type { DatasheetIntelligence, ReviewChunk, ReviewDocument, ReviewImage } from "../../types";
import { formatBytes, formatInteger, formatNumber } from "../../libs/format";
import { computeReviewHealth } from "../../libs/review/reviewQuality";

export function ReviewQaSummary({
  chunks,
  document,
  images,
  intelligence
}: {
  chunks: ReviewChunk[];
  document: ReviewDocument;
  images: ReviewImage[];
  intelligence: DatasheetIntelligence | null;
}) {
  const health = computeReviewHealth({ chunks, document, images, intelligence });
  const healthClass = `review-health-card ${health.level}`;

  return (
    <div className="review-qa-panel">
      <div className={healthClass}>
        <span>{health.label}</span>
        <strong>{health.autoApproveCandidate ? "Ready" : health.level === "blocked" ? "Blocked" : "Check"}</strong>
        <p>{health.summary}</p>
      </div>
      <div className="review-qa-metrics">
        <Metric label="Quality" value={formatNumber(document.avgQuality)} detail={`${formatInteger(document.lowQualityCount)} low quality`} />
        <Metric label="Text" value={formatInteger(document.chunkCount)} detail={`${formatInteger(document.rawChunkCount)} raw, ${formatInteger(document.droppedChunkCount)} dropped`} />
        <Metric label="Images" value={formatInteger(document.imageCount)} detail={`${formatInteger(document.ocrImageTextCount)} OCR indexed`} />
        <Metric label="File" value={formatBytes(document.sizeBytes)} detail={document.fileExtension || "source file"} />
      </div>
      {health.reasons.length || health.warnings.length ? (
        <div className="review-qa-notes">
          {health.reasons.map((reason) => <span key={reason} className="review-note blocked">{reason}</span>)}
          {health.warnings.map((warning) => <span key={warning} className="review-note attention">{warning}</span>)}
        </div>
      ) : null}
      <div className="review-decision-card">
        <div>
          <span className="section-kicker">Recommended action</span>
          <strong>{health.recommendation.action}</strong>
          <p>{health.recommendation.detail}</p>
        </div>
        <div className="review-inspection-list">
          <span className="section-kicker">Inspect first</span>
          <ul>
            {health.recommendation.inspect.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="review-qa-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
