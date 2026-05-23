import { useMemo, useState } from "react";
import { buildAssemblyPlan } from "../api";
import { errorMessage } from "../lib/errors";
import type { AppConfig, InventoryPartInput, ProjectCandidate } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { InventoryPartForm } from "./InventoryPartForm";
import { InventoryImportPanel } from "./InventoryImportPanel";
import { InventoryPartList } from "./InventoryPartList";
import { ProjectCandidateFilter, ProjectCandidateFilters } from "./ProjectCandidateFilters";
import { ProjectCandidateList } from "./ProjectCandidateList";
import { ProjectFinderSummary } from "./ProjectFinderSummary";
import { SectionHeader } from "./SectionHeader";
import { useInventory } from "../hooks/useInventory";

export function InventoryView({ config, isActive }: { config: AppConfig; isActive: boolean }) {
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
    findProjects,
    savePart,
    removePart,
    loadParts
  } = useInventory(isActive);
  const [saving, setSaving] = useState(false);
  const [buildingId, setBuildingId] = useState("");
  const [message, setMessage] = useState("");
  const [buildError, setBuildError] = useState("");
  const [candidateFilter, setCandidateFilter] = useState<ProjectCandidateFilter>("all");

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

  async function submitPart(part: InventoryPartInput) {
    setSaving(true);
    setMessage("");
    try {
      const saved = await savePart(part);
      if (saved) {
        setMessage(`${saved.displayName} added to inventory.`);
        return true;
      }
      return false;
    } finally {
      setSaving(false);
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
    <section className="inventory-grid">
      <aside className="inventory-panel">
        <SectionHeader title="Lab inventory" description={`${parts.length} stored parts`} />
        <InventoryPartForm saving={saving} onSave={submitPart} />
        <InventoryImportPanel
          onImported={(count) => {
            setMessage(`${count} inventory items imported.`);
            void loadParts();
          }}
        />
        <InventoryPartList parts={parts} loading={loading} onRemove={(partId) => void removePart(partId)} />
      </aside>
      <section className="inventory-results-panel">
        <div className="inventory-results-heading">
          <SectionHeader title="Project finder" description="Matches your parts against indexed source evidence." />
          <button className="primary-button" disabled={finding || !parts.length} onClick={() => void findProjects()}>
            {finding ? "Finding..." : "Find projects"}
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
        {candidates.length ? <ProjectCandidateFilters active={candidateFilter} counts={candidateCounts} onChange={setCandidateFilter} /> : null}
        <ProjectCandidateList
          candidates={filteredCandidates}
          finding={finding}
          buildingId={buildingId}
          onBuild={(candidate) => void createBenchPlan(candidate)}
        />
      </section>
    </section>
  );
}
