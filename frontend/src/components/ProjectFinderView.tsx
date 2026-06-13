import { useState } from "react";
import { buildAssemblyPlan } from "../libs/api";
import { rememberBenchPlanSelection } from "../libs/benchSelection";
import { errorMessage } from "../libs/errors";
import { formatNumber } from "../libs/format";
import { useElapsedSeconds } from "../hooks/useElapsedSeconds";
import { useInventory } from "../hooks/useInventory";
import type { AppConfig, ProjectCandidate, ProjectCandidateFilter, View } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { ProjectCandidateFilters } from "./ProjectCandidateFilters";
import { ProjectCandidateList } from "./ProjectCandidateList";
import { ProjectFinderSummary } from "./ProjectFinderSummary";
import { SectionHeader } from "./SectionHeader";

export function ProjectFinderView({
  config,
  isActive,
  setActiveView
}: {
  config: AppConfig;
  isActive: boolean;
  setActiveView: (view: View) => void;
}) {
  const {
    parts,
    candidates,
    inventoryCount,
    candidateCount,
    filterCount,
    candidateHasMore,
    buildableCount,
    needsPartsCount,
    missingPartSummary,
    loading,
    finding,
    error,
    findProjects
  } = useInventory(isActive);
  const [buildingId, setBuildingId] = useState("");
  const [message, setMessage] = useState("");
  const [buildError, setBuildError] = useState("");
  const [candidateFilter, setCandidateFilter] = useState<ProjectCandidateFilter>("all");
  const buildingElapsedSeconds = useElapsedSeconds(Boolean(buildingId));

  const candidateCounts: Record<ProjectCandidateFilter, number> = {
    all: candidateCount,
    buildable: buildableCount,
    "needs-parts": needsPartsCount
  };
  const activeFilterTotal = candidateCounts[candidateFilter] || filterCount || candidates.length;
  const hasFinderRun = candidateCount > 0 || buildableCount > 0 || needsPartsCount > 0 || candidates.length > 0;

  function runFinder(filter = candidateFilter, append = false) {
    void findProjects(filter, { append });
  }

  function changeCandidateFilter(filter: ProjectCandidateFilter) {
    setCandidateFilter(filter);
    if (hasFinderRun) {
      runFinder(filter);
    }
  }

  async function createBenchPlan(candidate: ProjectCandidate) {
    setBuildingId(candidate.id);
    setBuildError("");
    setMessage("");
    try {
      const response = await buildAssemblyPlan({
        objective: candidate.objective,
        model: config.defaultModel,
        topK: config.defaults.topK,
        distanceThreshold: config.defaults.distanceThreshold,
        maxTokens: config.defaults.maxTokens,
        strategy: config.defaults.strategy
      });
      if (response.plan) {
        rememberBenchPlanSelection(response.plan.id);
        setMessage(`Bench plan created: ${response.plan.title}`);
        setActiveView("bench");
      } else {
        setBuildError(response.error || "No Bench plan was created.");
      }
    } catch (err) {
      setBuildError(errorMessage(err, "Could not create Bench plan"));
    } finally {
      setBuildingId("");
    }
  }

  return (
    <section className="finder-workflow">
      <aside className="finder-control-panel">
        <SectionHeader title="Project finder" description="Scan indexed books against your lab inventory and turn matching ideas into Bench plans." />
        <div className="finder-readiness">
          <FinderMetric label="Inventory" value={parts.length} suffix="parts" />
          <FinderMetric label="Candidates" value={candidateCount || candidates.length} suffix="found" />
          <FinderMetric label="Buildable" value={buildableCount} suffix="ready" />
        </div>
        <div className="finder-actions">
          <button className="primary-button" disabled={finding || loading || !parts.length} onClick={() => runFinder()}>
            {finding ? "Finding projects..." : "Find projects"}
          </button>
          <button className="ghost-button" type="button" onClick={() => setActiveView("inventory")}>
            Manage inventory
          </button>
        </div>
        <ErrorMessage message={error || buildError} />
        {message ? <div className="success-message">{message}</div> : null}
        <ProjectFinderSummary
          inventoryCount={inventoryCount}
          buildableCount={buildableCount}
          needsPartsCount={needsPartsCount}
          missingPartSummary={missingPartSummary}
        />
      </aside>

      <section className="finder-results-panel">
        <div className="inventory-results-heading">
          <SectionHeader
            title="Build candidates"
            description={`${formatNumber(candidates.length)} visible of ${formatNumber(activeFilterTotal)} ${filterDescription(candidateFilter)} matches`}
          />
          {hasFinderRun ? (
            <ProjectCandidateFilters active={candidateFilter} counts={candidateCounts} loading={finding} onChange={changeCandidateFilter} />
          ) : null}
        </div>
        <ProjectCandidateList
          candidates={candidates}
          finding={finding}
          emptyLabel={hasFinderRun ? `No ${filterDescription(candidateFilter)} candidates found.` : "Run the finder after adding parts."}
          buildingId={buildingId}
          buildingElapsedSeconds={buildingElapsedSeconds}
          onBuild={(candidate) => void createBenchPlan(candidate)}
        />
        {candidateHasMore ? (
          <div className="project-candidate-pagination">
            <button className="ghost-button" type="button" disabled={finding} onClick={() => runFinder(candidateFilter, true)}>
              {finding ? "Loading..." : `Load more ${filterDescription(candidateFilter)} candidates`}
            </button>
          </div>
        ) : null}
      </section>
    </section>
  );
}

function filterDescription(filter: ProjectCandidateFilter) {
  if (filter === "buildable") {
    return "buildable";
  }
  if (filter === "needs-parts") {
    return "needs-parts";
  }
  return "project";
}

function FinderMetric({ label, value, suffix }: { label: string; value: number; suffix: string }) {
  return (
    <div className="finder-metric">
      <span>{label}</span>
      <strong>{formatNumber(value)}</strong>
      <small>{suffix}</small>
    </div>
  );
}
