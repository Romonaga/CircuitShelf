import { useCallback, useEffect, useState } from "react";
import { getAccountAIUsage, getEntityAIUsage, getSystemAIUsage } from "../api";
import { errorMessage } from "../lib/errors";
import type { AIUsageReport } from "../types";

export type AIUsageScope = "personal" | "entity" | "system";

export function useAIUsageReport(isActive: boolean, scope: AIUsageScope, days = 31) {
  const [report, setReport] = useState<AIUsageReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!isActive) {
      return;
    }
    try {
      setLoading(true);
      if (scope === "system") {
        setReport(await getSystemAIUsage(days));
      } else if (scope === "entity") {
        setReport(await getEntityAIUsage(days));
      } else {
        setReport(await getAccountAIUsage(days));
      }
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
