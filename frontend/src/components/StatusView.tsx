import type { StatusPayload } from "../types";
import { formatNumber, formatObject } from "../libs/format";
import { useLogTail } from "../hooks/useLogTail";
import { IngestStatusPanel } from "./IngestStatusPanel";
import { LogTailPanel } from "./LogTailPanel";
import { RuntimeBatchPanel } from "./RuntimeBatchPanel";
import { SectionHeader } from "./SectionHeader";
import { Stat } from "./Stat";
import { CollapsibleSection } from "./CollapsibleSection";
import { useUserPreference } from "../hooks/useUserPreference";

type StatusSectionId = "catalog" | "cache" | "database" | "runtime" | "ingestion" | "rawIngest" | "logs";
type StatusSectionPreference = Partial<Record<StatusSectionId, boolean>>;

const statusSectionDefaults: StatusSectionPreference = {
  catalog: false,
  cache: true,
  database: true,
  runtime: false,
  ingestion: false,
  rawIngest: true,
  logs: false
};

export function StatusView({
  status,
  refresh,
  isActive,
  isAdmin
}: {
  status: StatusPayload | null;
  refresh: () => void;
  isActive: boolean;
  isAdmin: boolean;
}) {
  const logTail = useLogTail(isActive && isAdmin);
  const sectionPreference = useUserPreference<StatusSectionPreference>("status.sections", {
    enabled: isActive,
    fallback: statusSectionDefaults,
    localStorageKey: "circuitshelf-status-sections"
  });
  const collapsedSections = { ...statusSectionDefaults, ...sectionPreference.value };

  function toggleSection(section: StatusSectionId) {
    void sectionPreference.setValue({
      ...collapsedSections,
      [section]: !collapsedSections[section]
    });
  }

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
      <CollapsibleSection
        title="Catalog"
        description="Indexed text, vectors, and image inventory."
        collapsed={Boolean(collapsedSections.catalog)}
        onToggle={() => toggleSection("catalog")}
      >
        <div className="status-grid">
          <Stat label="Chunks" value={formatNumber(status?.chunks)} />
          <Stat label="Documents" value={formatNumber(status?.sources)} />
          <Stat label="Text embeddings" value={formatNumber(status?.embeddings)} />
          <Stat label="Vector rows" value={formatNumber(status?.vectorEmbeddings)} />
          <Stat label="Image IDs" value={formatNumber(status?.imageIds)} />
          <Stat label="Image embeddings" value={formatNumber(status?.imageEmbeddings)} />
        </div>
      </CollapsibleSection>
      <CollapsibleSection
        title="Cache"
        description="Response cache size and hit/miss counters."
        collapsed={Boolean(collapsedSections.cache)}
        onToggle={() => toggleSection("cache")}
      >
        <pre className="json-view">{formatObject(status?.cacheStats)}</pre>
      </CollapsibleSection>
      <CollapsibleSection
        title="Database pool"
        description="PostgreSQL pool capacity and wait state."
        collapsed={Boolean(collapsedSections.database)}
        onToggle={() => toggleSection("database")}
      >
        <pre className="json-view">{formatObject(status?.databasePool)}</pre>
      </CollapsibleSection>
      <CollapsibleSection
        title="Runtime batches"
        description="GPU batch sizing used by embedding and reranking work."
        collapsed={Boolean(collapsedSections.runtime)}
        onToggle={() => toggleSection("runtime")}
      >
        <RuntimeBatchPanel batches={status?.runtimeBatches} />
      </CollapsibleSection>
      <CollapsibleSection
        title="Ingestion"
        description="Current indexing work, workers, file progress, and review readiness."
        collapsed={Boolean(collapsedSections.ingestion)}
        onToggle={() => toggleSection("ingestion")}
      >
        <IngestStatusPanel
          ingest={status?.ingest}
          workerBudget={status?.ingestWorkerBudget}
          runtimeBatches={status?.runtimeBatches}
          pendingReview={status?.pendingReview}
        />
      </CollapsibleSection>
      <CollapsibleSection
        title="Raw ingest payload"
        description="Developer diagnostic JSON for the active index worker."
        collapsed={Boolean(collapsedSections.rawIngest)}
        onToggle={() => toggleSection("rawIngest")}
      >
        <pre className="json-view">{formatObject(status?.ingest)}</pre>
      </CollapsibleSection>
      {isAdmin ? (
        <CollapsibleSection
          title="Trace log"
          description="Recent backend log tail."
          collapsed={Boolean(collapsedSections.logs)}
          onToggle={() => toggleSection("logs")}
        >
          <LogTailPanel tail={logTail.tail} loading={logTail.loading} error={logTail.error} onRefresh={logTail.refresh} />
        </CollapsibleSection>
      ) : null}
    </section>
  );
}
