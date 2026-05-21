import type { StatusPayload } from "../types";
import { formatNumber, formatObject } from "../lib/format";
import { SectionHeader } from "./SectionHeader";
import { Stat } from "./Stat";

export function StatusView({ status, refresh }: { status: StatusPayload | null; refresh: () => void }) {
  return (
    <section className="single-panel">
      <SectionHeader
        title="System status"
        description="Loaded vector catalog, image index, and cache state."
        actions={
        <button className="ghost-button" onClick={refresh}>
          Refresh
        </button>
        }
      />
      <div className="status-grid">
        <Stat label="Chunks" value={formatNumber(status?.chunks)} />
        <Stat label="Documents" value={formatNumber(status?.sources)} />
        <Stat label="Text embeddings" value={formatNumber(status?.embeddings)} />
        <Stat label="Vector rows" value={formatNumber(status?.vectorEmbeddings ?? status?.faissTotal)} />
        <Stat label="Image IDs" value={formatNumber(status?.imageIds)} />
        <Stat label="Image FAISS rows" value={formatNumber(status?.imageFaissTotal)} />
      </div>
      <h3>Cache</h3>
      <pre className="json-view">{formatObject(status?.cacheStats)}</pre>
    </section>
  );
}
