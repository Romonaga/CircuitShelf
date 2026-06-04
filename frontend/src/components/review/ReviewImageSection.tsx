import type { ReviewDocument, ReviewImage } from "../../types";
import { formatInteger } from "../../libs/format";

export function ReviewImageSection({
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
