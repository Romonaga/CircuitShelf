import type { ProjectMissingPartSummary } from "../types";

export function ProjectFinderSummary({
  inventoryCount,
  buildableCount,
  needsPartsCount,
  missingPartSummary
}: {
  inventoryCount: number;
  buildableCount: number;
  needsPartsCount: number;
  missingPartSummary: ProjectMissingPartSummary[];
}) {
  if (!inventoryCount && !buildableCount && !needsPartsCount && !missingPartSummary.length) {
    return null;
  }

  return (
    <section className="project-finder-summary">
      <div className="project-finder-stats">
        <SummaryStat label="Inventory parts" value={inventoryCount} />
        <SummaryStat label="Buildable" value={buildableCount} tone="ok" />
        <SummaryStat label="Need parts" value={needsPartsCount} tone="warn" />
      </div>
      <div className="project-gap-panel">
        <div>
          <h3>Parts that unlock more projects</h3>
          <p>Aggregated from the current Project Finder results.</p>
        </div>
        {missingPartSummary.length ? (
          <div className="project-gap-list">
            {missingPartSummary.map((part) => (
              <article key={`${part.type}-${part.name}`} className="project-gap-row">
                <div>
                  <strong>{part.name}</strong>
                  <small>
                    {part.type} | appears in {part.count} candidate{part.count === 1 ? "" : "s"}
                  </small>
                </div>
                <small>{part.exampleTitles.slice(0, 2).join(" | ")}</small>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state compact">No repeated missing parts detected in this run.</div>
        )}
      </div>
    </section>
  );
}

function SummaryStat({ label, value, tone = "" }: { label: string; value: number; tone?: string }) {
  return (
    <div className={`project-summary-stat ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
