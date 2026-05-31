import { useCallback, useEffect, useState } from "react";
import { getPerformanceReport } from "../api";
import { errorMessage } from "../lib/errors";
import type { PerformanceReport } from "../types";

export function usePerformanceReport(isActive: boolean, hours = 24, refreshKey = "") {
  const [report, setReport] = useState<PerformanceReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!isActive) {
      return;
    }
    try {
      setLoading(true);
      setReport(await getPerformanceReport(hours));
      setError("");
    } catch (err) {
      setError(errorMessage(err, "Could not load performance history"));
    } finally {
      setLoading(false);
    }
  }, [hours, isActive]);

  useEffect(() => {
    void refresh();
  }, [refresh, refreshKey]);

  return { report, loading, error, refresh };
}
