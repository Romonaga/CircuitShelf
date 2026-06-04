import { type MouseEvent, useState } from "react";
import type { AppConfig, AssemblyPlan, AssemblyPlanSummary } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { AssemblyPlanBuilder } from "./AssemblyPlanBuilder";
import { AssemblyPlanContextMenu, type AssemblyPlanContextMenuState } from "./AssemblyPlanContextMenu";
import { AssemblyPlanDetail } from "./AssemblyPlanDetail";
import { AssemblyPlanList } from "./AssemblyPlanList";
import { useAssemblyPlans } from "../hooks/useAssemblyPlans";
import { errorMessage } from "../libs/errors";

export function BenchView({ config, isActive }: { config: AppConfig; isActive: boolean }) {
  const [notice, setNotice] = useState("");
  const [deletingPlan, setDeletingPlan] = useState(false);
  const [contextMenu, setContextMenu] = useState<AssemblyPlanContextMenuState | null>(null);
  const {
    plans,
    selectedPlan,
    selectedPlanId,
    loadingPlans,
    loadingPlan,
    error,
    setSelectedPlan,
    setSelectedPlanId,
    loadPlans,
    removePlan,
    setError
  } = useAssemblyPlans(isActive);

  async function handlePlanCreated(plan: AssemblyPlan) {
    setNotice(`${plan.title} created.`);
    setSelectedPlan(plan);
    setSelectedPlanId(plan.id);
    await loadPlans();
  }

  function handlePlanUpdated(plan: AssemblyPlan) {
    setSelectedPlan(plan);
    void loadPlans();
  }

  function openPlanContextMenu(event: MouseEvent, plan: AssemblyPlanSummary) {
    event.preventDefault();
    setNotice("");
    setError("");
    setSelectedPlanId(plan.id);
    setContextMenu({ plan, x: event.clientX, y: event.clientY });
  }

  async function deletePlan(plan: AssemblyPlanSummary) {
    const confirmed = window.confirm(`Delete saved plan "${plan.title}"?\n\nThis removes the plan, checklist, notes, learning session, and photo checks.`);
    if (!confirmed) {
      setContextMenu(null);
      return;
    }

    setDeletingPlan(true);
    setError("");
    setNotice("");
    try {
      const deleted = await removePlan(plan.id);
      setNotice(`${deleted?.title || plan.title} deleted.`);
    } catch (err) {
      setError(errorMessage(err, "Could not delete saved plan"));
    } finally {
      setDeletingPlan(false);
      setContextMenu(null);
    }
  }

  return (
    <section className="bench-grid">
      <aside className="bench-sidebar">
        <AssemblyPlanBuilder
          config={config}
          onPlanCreated={(plan) => {
            void handlePlanCreated(plan);
          }}
        />
        <ErrorMessage message={error} />
        <ErrorMessage message={notice} className="success-message" />
        <AssemblyPlanList
          plans={plans}
          selectedPlanId={selectedPlanId}
          loading={loadingPlans}
          onSelect={(id) => {
            setNotice("");
            setError("");
            setSelectedPlanId(id);
          }}
          onOpenContextMenu={openPlanContextMenu}
        />
        <AssemblyPlanContextMenu
          menu={contextMenu}
          removing={deletingPlan}
          onClose={() => setContextMenu(null)}
          onDelete={(plan) => void deletePlan(plan)}
        />
      </aside>
      <section className="bench-detail-panel">
        <AssemblyPlanDetail plan={selectedPlan} loading={loadingPlan} config={config} onPlanUpdated={handlePlanUpdated} />
      </section>
    </section>
  );
}
