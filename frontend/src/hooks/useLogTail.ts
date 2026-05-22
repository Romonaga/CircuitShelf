import { useCallback, useEffect, useState } from "react";
import { getStatusLogTail } from "../api";
import { errorMessage } from "../lib/errors";
import type { LogTailPayload } from "../types";

const LOG_TAIL_LINES = 220;
const LOG_TAIL_REFRESH_MS = 3000;

export function useLogTail(enabled: boolean) {
  const [tail, setTail] = useState<LogTailPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async (silent = false) => {
    if (!enabled) {
      return;
    }
    if (!silent) {
      setLoading(true);
    }
    setError("");
    try {
      setTail(await getStatusLogTail(LOG_TAIL_LINES));
    } catch (err) {
      setError(errorMessage(err, "Could not load log tail"));
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    void refresh();
    const timer = window.setInterval(() => {
      void refresh(true);
    }, LOG_TAIL_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [enabled, refresh]);

  return { tail, loading, error, refresh };
}
