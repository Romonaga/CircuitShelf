import { useCallback, useEffect, useState } from "react";
import { getAssemblyPlan, getAssemblyPlans } from "../api";
import { errorMessage } from "../lib/errors";
import type { AssemblyPlan, AssemblyPlanSummary } from "../types";

export function useAssemblyPlans(isActive: boolean) {
  const [plans, setPlans] = useState<AssemblyPlanSummary[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [selectedPlan, setSelectedPlan] = useState<AssemblyPlan | null>(null);
  const [loadingPlans, setLoadingPlans] = useState(false);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [error, setError] = useState("");

  const loadPlans = useCallback(async () => {
    setLoadingPlans(true);
    setError("");
    try {
      const response = await getAssemblyPlans();
      setPlans(response.plans);
      setSelectedPlanId((current) => current || response.plans[0]?.id || "");
    } catch (err) {
      setError(errorMessage(err, "Could not load assembly plans"));
    } finally {
      setLoadingPlans(false);
    }
  }, []);

  const loadPlan = useCallback(async (planId: string) => {
    if (!planId) {
      setSelectedPlan(null);
      return;
    }
    setLoadingPlan(true);
    setError("");
    try {
      const response = await getAssemblyPlan(planId);
      setSelectedPlan(response.plan);
    } catch (err) {
      setError(errorMessage(err, "Could not load assembly plan"));
    } finally {
      setLoadingPlan(false);
    }
  }, []);

  useEffect(() => {
    if (isActive) {
      void loadPlans();
    }
  }, [isActive, loadPlans]);

  useEffect(() => {
    if (isActive) {
      void loadPlan(selectedPlanId);
    }
  }, [isActive, loadPlan, selectedPlanId]);

  return {
    plans,
    selectedPlan,
    selectedPlanId,
    loadingPlans,
    loadingPlan,
    error,
    setSelectedPlan,
    setSelectedPlanId,
    loadPlans,
    loadPlan,
    setError,
  };
}
