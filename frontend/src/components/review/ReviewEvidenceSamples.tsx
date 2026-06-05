import type { ReviewChunk, ReviewImage } from "../../types";
import { formatInteger } from "../../libs/format";
import { selectReviewEvidenceSamples } from "../../libs/review/reviewQuality";

export function ReviewEvidenceSamples({ chunks, images }: { chunks: ReviewChunk[]; images: ReviewImage[] }) {
  const samples = selectReviewEvidenceSamples(chunks, images);
  const hasEvidence = Boolean(samples.strongestText || samples.lowestQuality || samples.imageOcr || samples.image);

  if (!hasEvidence) {
    return <div className="empty-state compact">No representative evidence was loaded for this document.</div>;
  }

  return (
    <section className="review-evidence-panel">
      <div className="section-kicker">Evidence samples</div>
      <div className="review-evidence-grid">
        {samples.strongestText ? <EvidenceChunk title="Best text sample" chunk={samples.strongestText} /> : null}
        {samples.imageOcr ? <EvidenceChunk title="Image OCR sample" chunk={samples.imageOcr} /> : null}
        {samples.lowestQuality ? <EvidenceChunk title="Lowest quality sample" chunk={samples.lowestQuality} /> : null}
        {samples.image ? <EvidenceImage image={samples.image} /> : null}
      </div>
    </section>
  );
}

function EvidenceChunk({ title, chunk }: { title: string; chunk: ReviewChunk }) {
  return (
    <article className="review-evidence-card">
      <div className="chunk-meta">
        <strong>{title}</strong>
        <span>#{chunk.index}</span>
        {chunk.page ? <span>Page {chunk.page}</span> : null}
        <span>Quality {chunk.quality.toFixed(2)}</span>
        {chunk.isOcr ? <span>OCR</span> : null}
      </div>
      <p>{chunk.preview}</p>
    </article>
  );
}

function EvidenceImage({ image }: { image: ReviewImage }) {
  return (
    <article className="review-evidence-card review-evidence-image">
      <div className="chunk-meta">
        <strong>Image sample</strong>
        {image.page ? <span>Page {image.page}</span> : null}
        <span>{formatInteger(image.width)} x {formatInteger(image.height)}</span>
      </div>
      <img src={`data:${image.imageMimeType || "image/png"};base64,${image.imageBase64}`} alt={image.caption} />
      {image.ocrText ? <p>{image.ocrText.slice(0, 260)}</p> : null}
    </article>
  );
}
