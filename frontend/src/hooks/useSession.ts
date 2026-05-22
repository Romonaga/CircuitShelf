import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { logout as logoutApi, sessionStorageKey } from "../api";
import type { AppConfig, SessionUser } from "../types";

const ACTIVITY_EVENTS = ["keydown", "mousedown", "mousemove", "scroll", "touchstart"] as const;
const ACTIVITY_WRITE_INTERVAL_MS = 30_000;

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
      token: parsed.token,
      lastActivityAt: typeof parsed.lastActivityAt === "number" ? parsed.lastActivityAt : Date.now()
    };
  } catch {
    window.localStorage.removeItem(sessionStorageKey);
    return null;
  }
}

function timeoutMs(config: AppConfig | null): number {
  const seconds = Number(config?.sessionTimeoutSeconds ?? 0);
  return Number.isFinite(seconds) && seconds > 0 ? seconds * 1000 : 0;
}

function isExpired(session: SessionUser | null, config: AppConfig | null): boolean {
  const timeout = timeoutMs(config);
  if (!session || !timeout) {
    return false;
  }
  return Date.now() - (session.lastActivityAt ?? Date.now()) >= timeout;
}

export function useSession(config: AppConfig | null) {
  const [session, setSession] = useState<SessionUser | null>(() => readStoredSession());
  const lastWriteRef = useRef(0);
  const sessionRef = useRef<SessionUser | null>(session);
  const timeout = useMemo(() => timeoutMs(config), [config]);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    if (config && !config.authConfigured && !session) {
      setSession({ username: "local", isAdmin: true, token: "" });
    }
  }, [config, session]);

  const clearSession = useCallback(() => {
    window.localStorage.removeItem(sessionStorageKey);
    setSession(config?.authConfigured ? null : { username: "local", isAdmin: true, token: "", lastActivityAt: Date.now() });
  }, [config]);

  const logout = useCallback(() => {
    void logoutApi().catch(() => undefined);
    clearSession();
  }, [clearSession]);

  const login = useCallback((nextSession: SessionUser) => {
    const storedSession = { ...nextSession, lastActivityAt: Date.now() };
    window.localStorage.setItem(sessionStorageKey, JSON.stringify(storedSession));
    setSession(storedSession);
  }, []);

  useEffect(() => {
    if (!config?.authConfigured || !session) {
      return;
    }
    if (isExpired(session, config)) {
      logout();
    }
  }, [config, logout, session]);

  useEffect(() => {
    if (!config?.authConfigured || !session || !timeout) {
      return;
    }

    const touchActivity = () => {
      const current = sessionRef.current;
      if (!current) {
        return;
      }
      const now = Date.now();
      if (now - lastWriteRef.current < ACTIVITY_WRITE_INTERVAL_MS) {
        return;
      }
      lastWriteRef.current = now;
      const nextSession = { ...current, lastActivityAt: now };
      sessionRef.current = nextSession;
      window.localStorage.setItem(sessionStorageKey, JSON.stringify(nextSession));
      setSession(nextSession);
    };

    ACTIVITY_EVENTS.forEach((eventName) => window.addEventListener(eventName, touchActivity, { passive: true }));
    const timer = window.setInterval(() => {
      if (isExpired(sessionRef.current, config)) {
        logout();
      }
    }, Math.min(timeout, 60_000));

    return () => {
      ACTIVITY_EVENTS.forEach((eventName) => window.removeEventListener(eventName, touchActivity));
      window.clearInterval(timer);
    };
  }, [config, logout, session, timeout]);

  useEffect(() => {
    window.addEventListener("circuitshelf-auth-expired", clearSession);
    return () => window.removeEventListener("circuitshelf-auth-expired", clearSession);
  }, [clearSession]);

  return { user: session, login, logout };
}
