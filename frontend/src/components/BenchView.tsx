import { useState } from "react";
import type { AppConfig, AssemblyPlan } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { AssemblyPlanBuilder } from "./AssemblyPlanBuilder";
import { AssemblyPlanDetail } from "./AssemblyPlanDetail";
import { AssemblyPlanList } from "./AssemblyPlanList";
import { useAssemblyPlans } from "../hooks/useAssemblyPlans";

export function BenchView({ config, isActive }: { config: AppConfig; isActive: boolean }) {
  const [notice, setNotice] = useState("");
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
        <AssemblyPlanList plans={plans} selectedPlanId={selectedPlanId} loading={loadingPlans} onSelect={(id) => {
          setNotice("");
          setError("");
          setSelectedPlanId(id);
        }} />
      </aside>
      <section className="bench-detail-panel">
        <AssemblyPlanDetail plan={selectedPlan} loading={loadingPlan} config={config} onPlanUpdated={handlePlanUpdated} />
      </section>
    </section>
  );
}
