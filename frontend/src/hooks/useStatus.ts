import { useCallback, useEffect, useState } from "react";
import { getStatus } from "../api";
import { errorMessage } from "../lib/errors";
import type { StatusPayload } from "../types";

export function useStatus() {
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [error, setError] = useState("");

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await getStatus());
      setError("");
    } catch (err) {
      setError(errorMessage(err, "Could not load status"));
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    if (!status?.ingest?.running) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshStatus();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [refreshStatus, status?.ingest?.running]);

  return { status, statusError: error, refreshStatus };
}
