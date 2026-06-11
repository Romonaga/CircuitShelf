const BENCH_SELECTED_PLAN_KEY = "circuitshelf.bench.selectedPlanId";

export function rememberBenchPlanSelection(planId: string) {
  if (!planId || typeof window === "undefined") {
    return;
  }
  window.sessionStorage.setItem(BENCH_SELECTED_PLAN_KEY, planId);
}

export function consumeBenchPlanSelection(): string {
  if (typeof window === "undefined") {
    return "";
  }
  const planId = window.sessionStorage.getItem(BENCH_SELECTED_PLAN_KEY) || "";
  if (planId) {
    window.sessionStorage.removeItem(BENCH_SELECTED_PLAN_KEY);
  }
  return planId;
}
