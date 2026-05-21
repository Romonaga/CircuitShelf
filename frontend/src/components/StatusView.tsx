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
        <Stat label="Vector rows" value={formatNumber(status?.vectorEmbeddings)} />
        <Stat label="Image IDs" value={formatNumber(status?.imageIds)} />
        <Stat label="Image embeddings" value={formatNumber(status?.imageEmbeddings)} />
      </div>
      <h3>Cache</h3>
      <pre className="json-view">{formatObject(status?.cacheStats)}</pre>
      <h3>Ingestion</h3>
      <pre className="json-view">{formatObject(status?.ingest)}</pre>
    </section>
  );
}
