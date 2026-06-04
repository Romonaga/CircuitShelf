import { useMemo, useState } from "react";
import { buildAssemblyPlan } from "../api";
import { errorMessage } from "../libs/errors";
import { formatNumber } from "../libs/format";
import { useElapsedSeconds } from "../hooks/useElapsedSeconds";
import { useInventory } from "../hooks/useInventory";
import type { AppConfig, ProjectCandidate, View } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { ProjectCandidateFilter, ProjectCandidateFilters } from "./ProjectCandidateFilters";
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

  const filteredCandidates = useMemo(() => {
    if (candidateFilter === "buildable") {
      return candidates.filter((candidate) => candidate.buildable);
    }
    if (candidateFilter === "needs-parts") {
      return candidates.filter((candidate) => !candidate.buildable);
    }
    return candidates;
  }, [candidateFilter, candidates]);

  const candidateCounts = useMemo(
    () => ({
      all: candidates.length,
      buildable: candidates.filter((candidate) => candidate.buildable).length,
      "needs-parts": candidates.filter((candidate) => !candidate.buildable).length
    }),
    [candidates]
  );

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
        setMessage(`Bench plan created: ${response.plan.title}`);
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
          <FinderMetric label="Candidates" value={candidates.length} suffix="found" />
          <FinderMetric label="Buildable" value={buildableCount || candidateCounts.buildable} suffix="ready" />
        </div>
        <div className="finder-actions">
          <button className="primary-button" disabled={finding || loading || !parts.length} onClick={() => void findProjects()}>
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
          <SectionHeader title="Build candidates" description={`${formatNumber(filteredCandidates.length)} visible project matches`} />
          {candidates.length ? <ProjectCandidateFilters active={candidateFilter} counts={candidateCounts} onChange={setCandidateFilter} /> : null}
        </div>
        <ProjectCandidateList
          candidates={filteredCandidates}
          finding={finding}
          buildingId={buildingId}
          buildingElapsedSeconds={buildingElapsedSeconds}
          onBuild={(candidate) => void createBenchPlan(candidate)}
        />
      </section>
    </section>
  );
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
