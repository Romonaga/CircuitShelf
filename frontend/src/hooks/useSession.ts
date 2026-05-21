import { useCallback, useEffect, useState } from "react";
import type { AppConfig } from "../types";

const storageKey = "circuitshelf-user";

export function useSession(config: AppConfig | null) {
  const [user, setUser] = useState(() => window.localStorage.getItem(storageKey) || "");

  useEffect(() => {
    if (config && !config.authConfigured && !user) {
      setUser("local");
    }
  }, [config, user]);

  const login = useCallback((name: string) => {
    window.localStorage.setItem(storageKey, name);
    setUser(name);
  }, []);

  const logout = useCallback(() => {
    window.localStorage.removeItem(storageKey);
    setUser(config?.authConfigured ? "" : "local");
  }, [config]);

  return { user, login, logout };
}
