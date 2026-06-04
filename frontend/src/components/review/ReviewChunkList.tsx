import type { ReviewChunk } from "../../types";
import { formatInteger } from "../../libs/format";

export function ReviewChunkList({ chunks, detailBusy }: { chunks: ReviewChunk[]; detailBusy: boolean }) {
  return (
    <div className="chunk-table">
      {chunks.map((chunk) => (
        <article key={chunk.index} className={chunk.quality < 0.35 ? "chunk-row warning-row" : "chunk-row"}>
          <div className="chunk-meta">
            <strong>#{chunk.index}</strong>
            <span>{chunk.section}</span>
            <span>{chunk.category}</span>
            <span>{formatInteger(chunk.tokens)} tokens</span>
            <span>Quality {chunk.quality.toFixed(2)}</span>
            {chunk.page ? <span>Page {chunk.page}</span> : null}
            {chunk.sourceImageId ? <span>Image {chunk.sourceImageId}</span> : null}
            {chunk.isOcr ? <span>OCR</span> : null}
            {chunk.hasMath ? <span>Math</span> : null}
          </div>
          <p>{chunk.preview}</p>
          {chunk.qualityFlags.length ? <small>{chunk.qualityFlags.join(", ")}</small> : null}
        </article>
      ))}
      {!detailBusy && !chunks.length ? <div className="empty-state">Select a document to inspect review chunks.</div> : null}
    </div>
  );
}
