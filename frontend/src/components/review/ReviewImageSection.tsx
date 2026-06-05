import { useEffect, useMemo, useState } from "react";
import type { ReviewDocument, ReviewImage } from "../../types";
import { formatInteger } from "../../libs/format";

function pageSortValue(page: ReviewImage["page"]): number {
  if (page === null || page === undefined || page === "") {
    return Number.MAX_SAFE_INTEGER;
  }
  const parsed = Number(page);
  return Number.isFinite(parsed) ? parsed : Number.MAX_SAFE_INTEGER - 1;
}

function pageLabel(page: ReviewImage["page"]): string {
  if (page === null || page === undefined || page === "") {
    return "Unassigned page";
  }
  return `Page ${page}`;
}

export function ReviewImageSection({
  defaultOpen = true,
  detailBusy,
  images,
  selectedDocument
}: {
  defaultOpen?: boolean;
  detailBusy: boolean;
  images: ReviewImage[];
  selectedDocument: ReviewDocument | null;
}) {
  const [open, setOpen] = useState(defaultOpen && images.length > 0);
  const imageSignature = images.map((image) => image.imageKey).join("|");
  const imageGroups = useMemo(() => {
    const groups = new Map<string, { label: string; page: ReviewImage["page"]; images: ReviewImage[] }>();
    for (const image of images) {
      const key = String(image.page ?? "unassigned");
      const existing = groups.get(key);
      if (existing) {
        existing.images.push(image);
      } else {
        groups.set(key, { label: pageLabel(image.page), page: image.page, images: [image] });
      }
    }
    return [...groups.values()].sort((left, right) => pageSortValue(left.page) - pageSortValue(right.page));
  }, [images]);

  useEffect(() => {
    setOpen(defaultOpen && images.length > 0);
  }, [defaultOpen, imageSignature, images.length]);

  return (
    <details
      className="review-image-details"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>Image assets ({formatInteger(images.length)})</summary>
      <div className="review-image-pages">
        {imageGroups.map((group) => (
          <section key={group.label} className="review-image-page">
            <div className="review-image-page-header">
              <strong>{group.label}</strong>
              <span>{formatInteger(group.images.length)} images</span>
            </div>
            <div className="review-images">
              {group.images.map((image) => (
                <article key={image.imageKey} className="review-image-card">
                  <div className="chunk-meta">
                    <strong>{image.caption}</strong>
                    <span>{formatInteger(image.width)} x {formatInteger(image.height)}</span>
                  </div>
                  <img src={`data:${image.imageMimeType || "image/png"};base64,${image.imageBase64}`} alt={image.caption} />
                </article>
              ))}
            </div>
          </section>
        ))}
        {selectedDocument && !detailBusy && !images.length ? <div className="empty-state compact">No image assets were extracted for this document.</div> : null}
      </div>
    </details>
  );
}
