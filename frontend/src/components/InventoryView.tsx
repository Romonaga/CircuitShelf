import { useState } from "react";
import { buildAssemblyPlan } from "../api";
import { errorMessage } from "../lib/errors";
import type { AppConfig, InventoryPartInput, ProjectCandidate } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { InventoryPartForm } from "./InventoryPartForm";
import { InventoryPartList } from "./InventoryPartList";
import { ProjectCandidateList } from "./ProjectCandidateList";
import { SectionHeader } from "./SectionHeader";
import { useInventory } from "../hooks/useInventory";

export function InventoryView({ config, isActive }: { config: AppConfig; isActive: boolean }) {
  const { parts, candidates, loading, finding, error, findProjects, savePart, removePart } = useInventory(isActive);
  const [saving, setSaving] = useState(false);
  const [buildingId, setBuildingId] = useState("");
  const [message, setMessage] = useState("");
  const [buildError, setBuildError] = useState("");

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
        <ProjectCandidateList
          candidates={candidates}
          finding={finding}
          buildingId={buildingId}
          onBuild={(candidate) => void createBenchPlan(candidate)}
        />
      </section>
    </section>
  );
}
