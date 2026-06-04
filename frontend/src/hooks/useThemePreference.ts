import { useEffect, useState } from "react";
import { getUserPreference, updateUserPreference } from "../libs/api";

export type ThemeMode = "light" | "dark";

const preferenceKey = "ui.theme";
const storageKey = "circuitshelf-theme";

function normalizeTheme(value: unknown): ThemeMode {
  if (value === "dark" || (typeof value === "object" && value !== null && "theme" in value && (value as { theme?: unknown }).theme === "dark")) {
    return "dark";
  }
  return "light";
}

function readStoredTheme(): ThemeMode {
  try {
    return normalizeTheme(window.localStorage.getItem(storageKey));
  } catch {
    return "light";
  }
}

function storeTheme(theme: ThemeMode) {
  try {
    window.localStorage.setItem(storageKey, theme);
  } catch {
    // Theme preference is cosmetic; ignore storage failures.
  }
}

export function useThemePreference(canSync: boolean) {
  const [theme, setTheme] = useState<ThemeMode>(() => readStoredTheme());
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    storeTheme(theme);
  }, [theme]);

  useEffect(() => {
    if (!canSync) {
      setLoaded(true);
      return;
    }
    let cancelled = false;
    async function loadTheme() {
      try {
        const response = await getUserPreference<{ theme?: ThemeMode }>(preferenceKey);
        if (!cancelled && response.value?.theme) {
          setTheme(normalizeTheme(response.value.theme));
        }
      } catch {
        // Local storage keeps the UI usable if preferences are unavailable.
      } finally {
        if (!cancelled) {
          setLoaded(true);
        }
      }
    }
    void loadTheme();
    return () => {
      cancelled = true;
    };
  }, [canSync]);

  useEffect(() => {
    if (!canSync || !loaded) {
      return;
    }
    void updateUserPreference(preferenceKey, { theme }).catch(() => undefined);
  }, [canSync, loaded, theme]);

  return {
    theme,
    setTheme,
    toggleTheme: () => setTheme((current) => (current === "dark" ? "light" : "dark"))
  };
}
