import { useCallback, useEffect, useState } from "react";
import { logout as logoutApi, sessionStorageKey } from "../api";
import type { AppConfig, SessionUser } from "../types";

function readStoredSession(): SessionUser | null {
  try {
    const raw = window.localStorage.getItem(sessionStorageKey);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<SessionUser>;
    if (typeof parsed !== "object" || !parsed || !parsed.username || typeof parsed.token !== "string") {
      window.localStorage.removeItem(sessionStorageKey);
      return null;
    }
    return {
      username: parsed.username,
      isAdmin: Boolean(parsed.isAdmin),
      token: parsed.token
    };
  } catch {
    window.localStorage.removeItem(sessionStorageKey);
    return null;
  }
}

export function useSession(config: AppConfig | null) {
  const [session, setSession] = useState<SessionUser | null>(() => readStoredSession());

  useEffect(() => {
    if (config && !config.authConfigured && !session) {
      setSession({ username: "local", isAdmin: true, token: "" });
    }
  }, [config, session]);

  const login = useCallback((nextSession: SessionUser) => {
    window.localStorage.setItem(sessionStorageKey, JSON.stringify(nextSession));
    setSession(nextSession);
  }, []);

  const logout = useCallback(() => {
    void logoutApi().catch(() => undefined);
    window.localStorage.removeItem(sessionStorageKey);
    setSession(config?.authConfigured ? null : { username: "local", isAdmin: true, token: "" });
  }, [config]);

  return { user: session, login, logout };
}
