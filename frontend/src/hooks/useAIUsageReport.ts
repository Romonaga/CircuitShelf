import { useCallback, useEffect, useState } from "react";
import { getEntityAIUsage, getSystemAIUsage } from "../api";
import { errorMessage } from "../lib/errors";
import type { AIUsageReport } from "../types";

export function useAIUsageReport(isActive: boolean, scope: "entity" | "system", days = 31) {
  const [report, setReport] = useState<AIUsageReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!isActive) {
      return;
    }
    try {
      setLoading(true);
      setReport(scope === "system" ? await getSystemAIUsage(days) : await getEntityAIUsage(days));
      setError("");
    } catch (err) {
      setError(errorMessage(err, "Could not load AI usage"));
    } finally {
      setLoading(false);
    }
  }, [days, isActive, scope]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { report, loading, error, refresh };
}
