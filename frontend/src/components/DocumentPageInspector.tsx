import { useState } from "react";
import type { DocumentPage } from "../types";
import { formatInteger } from "../lib/format";

type InspectorMode = "chunks" | "images";

export function DocumentPageInspector({ page }: { page: DocumentPage }) {
  const [mode, setMode] = useState<InspectorMode>("chunks");

  return (
    <div className="document-page-inspector">
      <div className="inspector-tabs" role="tablist" aria-label={`Page ${page.page} content`}>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "chunks"}
          className={mode === "chunks" ? "tab-button active" : "tab-button"}
          onClick={() => setMode("chunks")}
        >
          Chunks ({formatInteger(page.chunks.length)})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "images"}
          className={mode === "images" ? "tab-button active" : "tab-button"}
          onClick={() => setMode("images")}
        >
          Images ({formatInteger(page.images.length)})
        </button>
      </div>

      <div className="document-page-content">
        {mode === "images" ? (
          <div className="document-images">
            {page.images.map((image) => (
              <article key={image.imageKey} className="document-image-card">
                <div className="chunk-meta">
                  <strong>{image.caption}</strong>
                  <span>{image.imageKey}</span>
                </div>
                <img src={`data:image/png;base64,${image.imageBase64}`} alt={image.caption} />
              </article>
            ))}
            {!page.images.length ? <div className="empty-state compact">No rendered images for this page.</div> : null}
          </div>
        ) : (
          <div className="chunk-table">
            {page.chunks.map((chunk) => (
              <article key={chunk.index} className="chunk-row">
                <div className="chunk-meta">
                  <strong>#{chunk.index}</strong>
                  <span>{chunk.section}</span>
                  <span>{chunk.category}</span>
                  <span>{formatInteger(chunk.tokens)} tokens</span>
                  {chunk.sourceImageId ? <span>Linked image: {chunk.sourceImageId}</span> : null}
                </div>
                <p>{chunk.preview}</p>
              </article>
            ))}
            {!page.chunks.length ? <div className="empty-state compact">No text chunks for this page.</div> : null}
          </div>
        )}
      </div>
    </div>
  );
}
