import type { DocumentImage } from "../types";
import { formatInteger } from "../libs/format";

export function DocumentImageGallery({ images }: { images: DocumentImage[] }) {
  return (
    <details className="document-image-details">
      <summary>Image assets ({formatInteger(images.length)})</summary>
      {images.length ? (
        <div className="document-image-grid">
          {images.map((image) => (
            <article key={image.imageKey} className="document-image-card">
              <div>
                <strong>{image.caption}</strong>
                <span>{image.imageKey}</span>
                {image.page ? <span>Page {image.page}</span> : null}
              </div>
              <img src={`data:${image.imageMimeType || "image/png"};base64,${image.imageBase64}`} alt={image.caption} />
              {image.ocrText ? <p>{image.ocrText.slice(0, 220)}</p> : null}
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state compact">No image assets were extracted for this page.</div>
      )}
    </details>
  );
}
