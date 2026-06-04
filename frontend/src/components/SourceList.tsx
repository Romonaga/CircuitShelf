import type { SourceSummary } from "../types";
import { formatNumber } from "../libs/format";

function pageLabel(pages: SourceSummary["pages"]): string {
  if (!pages?.length) {
    return "page unknown";
  }
  const visiblePages = pages.slice(0, 8);
  const suffix = pages.length > visiblePages.length ? `, +${pages.length - visiblePages.length}` : "";
  return `page${pages.length === 1 ? "" : "s"} ${visiblePages.join(", ")}${suffix}`;
}

export function SourceList({ sources }: { sources: SourceSummary[] }) {
  if (!sources.length) {
    return <div className="empty-state compact">No sources yet.</div>;
  }

  return (
    <div className="source-list">
      {sources.map((source, index) => (
        <details key={`${source.source}-${index}`} className="source-item">
          <summary>
            <span className="source-title">{source.displayName || source.source}</span>
            <small className="source-pages" title={source.pages?.length ? `Pages ${source.pages.join(", ")}` : undefined}>
              {pageLabel(source.pages)}
            </small>
          </summary>
          <div className="source-detail">
            <div className="source-meta">
              <span>{source.chunkCount ?? source.chunks?.length ?? 0} chunks used</span>
              <span>{source.source}</span>
            </div>
            <div className="source-chunks">
              {(source.chunks ?? []).map((chunk) => (
                <article className="source-chunk" key={`${chunk.index}-${chunk.page}-${chunk.preview}`}>
                  <div className="source-chunk-meta">
                    <span>Page {chunk.page ?? "unknown"}</span>
                    <span>{chunk.section || "Unknown section"}</span>
                    <span>{chunk.category || "Uncategorized"}</span>
                    {chunk.distance !== undefined && chunk.distance !== null ? <span>Distance {formatNumber(chunk.distance)}</span> : null}
                  </div>
                  {chunk.preview ? <p>{chunk.preview}</p> : null}
                </article>
              ))}
            </div>
          </div>
        </details>
      ))}
    </div>
  );
}
