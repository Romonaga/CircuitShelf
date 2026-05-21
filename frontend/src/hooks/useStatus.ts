import { useCallback, useEffect, useState } from "react";
import { getStatus } from "../api";
import { errorMessage } from "../lib/errors";
import type { StatusPayload } from "../types";

function normalizedInterval(value: number | undefined, fallback: number, minimum: number): number {
  const seconds = Number.isFinite(value) ? Number(value) : fallback;
  return Math.max(minimum, seconds) * 1000;
}

export function useStatus(idlePollSeconds = 15, activePollSeconds = 3) {
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
    const interval = status?.ingest?.running
      ? normalizedInterval(activePollSeconds, 3, 1)
      : normalizedInterval(idlePollSeconds, 15, 5);
    const timer = window.setInterval(() => {
      void refreshStatus();
    }, interval);
    return () => window.clearInterval(timer);
  }, [activePollSeconds, idlePollSeconds, refreshStatus, status?.ingest?.running]);

  return { status, statusError: error, refreshStatus };
}
