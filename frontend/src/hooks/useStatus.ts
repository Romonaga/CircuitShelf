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

  return { status, statusError: error, refreshStatus };
}
