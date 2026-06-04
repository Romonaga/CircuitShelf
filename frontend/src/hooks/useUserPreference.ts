import { useCallback, useEffect, useState } from "react";
import { getUserPreference, updateUserPreference } from "../api";

type UseUserPreferenceOptions<T> = {
  enabled?: boolean;
  fallback?: T;
  localStorageKey?: string;
};

function readLocalPreference<T>(key: string | undefined, fallback: T): T {
  if (!key) {
    return fallback;
  }
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? { ...fallback, ...JSON.parse(raw) } : fallback;
  } catch {
    return fallback;
  }
}

export function useUserPreference<T extends Record<string, unknown>>(
  preferenceKey: string,
  options: UseUserPreferenceOptions<T> = {}
) {
  const enabled = options.enabled ?? true;
  const fallback = options.fallback ?? ({} as T);
  const [value, setValue] = useState<T>(() => readLocalPreference(options.localStorageKey, fallback));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!enabled) {
      return () => {
        cancelled = true;
      };
    }

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await getUserPreference<T>(preferenceKey);
        if (!cancelled) {
          setValue({ ...fallback, ...(response.value ?? {}) });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error("Could not load preference"));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [enabled, fallback, preferenceKey]);

  const save = useCallback(
    async (nextValue: T | ((current: T) => T)) => {
      const resolved = typeof nextValue === "function" ? (nextValue as (current: T) => T)(value) : nextValue;
      setValue(resolved);
      if (options.localStorageKey) {
        try {
          window.localStorage.setItem(options.localStorageKey, JSON.stringify(resolved));
        } catch {
          // Local storage is only a fast fallback; DB persistence is authoritative.
        }
      }
      if (enabled) {
        await updateUserPreference(preferenceKey, resolved);
      }
      return resolved;
    },
    [enabled, options.localStorageKey, preferenceKey, value]
  );

  return { value, setValue: save, loading, error };
}
