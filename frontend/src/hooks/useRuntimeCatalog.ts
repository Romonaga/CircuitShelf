import { useCallback, useEffect, useState } from "react";
import { getRuntimeCatalog } from "../api";
import { errorMessage } from "../libs/errors";
import type { RuntimeCatalog } from "../types";

export function useRuntimeCatalog(isActive: boolean) {
  const [catalog, setCatalog] = useState<RuntimeCatalog | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setCatalog(await getRuntimeCatalog());
    } catch (err) {
      setError(errorMessage(err, "Could not load runtime catalog"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isActive) {
      void refresh();
    }
  }, [isActive, refresh]);

  return { catalog, loading, error, refresh };
}
