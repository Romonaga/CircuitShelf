import type { DocumentPage } from "../types";
import { formatInteger } from "../lib/format";

export function DocumentPageInspector({ page }: { page: DocumentPage }) {
  return (
    <div className="document-page-inspector">
      <div className="document-page-toolbar">
        <strong>Page {page.page}</strong>
        <span>{formatInteger(page.chunks.length)} chunks</span>
        <span>{formatInteger(page.images.length)} image assets available to retrieval</span>
      </div>

      <div className="document-chunk-list">
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
    </div>
  );
}
