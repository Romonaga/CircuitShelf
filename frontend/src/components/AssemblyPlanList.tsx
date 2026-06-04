import type { MouseEvent } from "react";
import { formatNumber } from "../libs/format";
import type { AssemblyPlanSummary } from "../types";

export function AssemblyPlanList({
  plans,
  selectedPlanId,
  loading,
  onSelect,
  onOpenContextMenu
}: {
  plans: AssemblyPlanSummary[];
  selectedPlanId: string;
  loading: boolean;
  onSelect: (planId: string) => void;
  onOpenContextMenu: (event: MouseEvent, plan: AssemblyPlanSummary) => void;
}) {
  return (
    <div className="assembly-plan-list">
      <h3>{loading ? "Loading plans..." : "Saved plans"}</h3>
      {plans.map((plan) => {
        const progress = plan.stepCount ? Math.round((plan.completedStepCount / plan.stepCount) * 100) : 0;
        return (
          <button
            key={plan.id}
            className={plan.id === selectedPlanId ? "assembly-plan-row active" : "assembly-plan-row"}
            type="button"
            onClick={() => onSelect(plan.id)}
            onContextMenu={(event) => onOpenContextMenu(event, plan)}
          >
            <strong>{plan.title}</strong>
            <span>{plan.componentName || plan.componentType || "Circuit build"}</span>
            <small>
              {plan.completedStepCount}/{plan.stepCount} steps | {formatNumber(progress)}%
            </small>
          </button>
        );
      })}
      {!loading && !plans.length ? <div className="empty-state compact">No assembly plans yet.</div> : null}
    </div>
  );
}
