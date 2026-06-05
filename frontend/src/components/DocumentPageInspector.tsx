import type { DocumentPage } from "../types";
import { formatInteger } from "../libs/format";
import { DocumentImageGallery } from "./DocumentImageGallery";

export function DocumentPageInspector({ page }: { page: DocumentPage }) {
  const nativeChunks = page.chunks.filter((chunk) => !chunk.sourceImageId && (chunk.chunkType ?? "native") !== "ocr");
  const ocrChunks = page.chunks.filter((chunk) => chunk.sourceImageId || (chunk.chunkType ?? "native") === "ocr");

  return (
    <div className="document-page-inspector">
      <div className="document-page-toolbar">
        <strong>Page {page.page}</strong>
        <span>{formatInteger(nativeChunks.length)} native text chunks</span>
        <span>{formatInteger(ocrChunks.length)} OCR text chunks</span>
        <span>{formatInteger(page.images.length)} image assets</span>
      </div>

      <DocumentImageGallery images={page.images} defaultOpen={!nativeChunks.length && page.images.length > 0} />

      <div className="document-chunk-list">
        <ChunkGroup title="Native PDF text" chunks={nativeChunks} emptyText="No native PDF text chunks were indexed for this page." />
        <ChunkGroup title="Image OCR text" chunks={ocrChunks} emptyText="No OCR text chunks were indexed for this page." />
      </div>
    </div>
  );
}

function ChunkGroup({ title, chunks, emptyText }: { title: string; chunks: DocumentPage["chunks"]; emptyText: string }) {
  return (
    <section className="document-chunk-group">
      <div className="document-chunk-group-title">
        <strong>{title}</strong>
        <span>{formatInteger(chunks.length)} chunks</span>
      </div>
      {chunks.map((chunk) => (
        <article key={chunk.index} className="chunk-row">
          <div className="chunk-meta">
            <strong>#{chunk.index}</strong>
            <span>{chunk.section}</span>
            <span>{chunk.category}</span>
            <span>{chunk.chunkType ?? "native"}</span>
            <span>{formatInteger(chunk.tokens)} tokens</span>
            {chunk.sourceImageId ? <span>Linked image: {chunk.sourceImageId}</span> : null}
          </div>
          <p>{chunk.preview}</p>
        </article>
      ))}
      {!chunks.length ? <div className="empty-state compact">{emptyText}</div> : null}
    </section>
  );
}
