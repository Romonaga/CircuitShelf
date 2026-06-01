import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getMe, logout as logoutApi, sessionStorageKey } from "../api";
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
      userId: typeof parsed.userId === "number" ? parsed.userId : undefined,
      username: parsed.username,
      isAdmin: Boolean(parsed.isAdmin),
      canManageSystem: Boolean(parsed.canManageSystem),
      forcePasswordChange: Boolean(parsed.forcePasswordChange),
      entity: parsed.entity ?? null,
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

  const clearSession = useCallback(() => {
    window.localStorage.removeItem(sessionStorageKey);
    setSession(null);
  }, []);

  const logout = useCallback(() => {
    void logoutApi().catch(() => undefined);
    clearSession();
  }, [clearSession]);

  const login = useCallback((nextSession: SessionUser) => {
    const storedSession = { ...nextSession, lastActivityAt: Date.now() };
    window.localStorage.setItem(sessionStorageKey, JSON.stringify(storedSession));
    setSession(storedSession);
  }, []);

  const refreshSession = useCallback(async () => {
    const currentSession = sessionRef.current;
    if (!config?.authConfigured || !currentSession?.token) {
      return;
    }
    const currentUser = await getMe();
    const refreshedSession: SessionUser = {
      ...currentSession,
      userId: currentUser.userId,
      username: currentUser.username,
      isAdmin: Boolean(currentUser.isAdmin),
      canManageSystem: Boolean(currentUser.canManageSystem),
      forcePasswordChange: Boolean(currentUser.forcePasswordChange),
      entity: currentUser.entity ?? null,
      lastActivityAt: Date.now()
    };
    sessionRef.current = refreshedSession;
    window.localStorage.setItem(sessionStorageKey, JSON.stringify(refreshedSession));
    setSession(refreshedSession);
  }, [config?.authConfigured]);

  useEffect(() => {
    if (!config?.authConfigured || !session?.token) {
      return;
    }
    let active = true;
    refreshSession().catch(() => {
      if (active) {
        return undefined;
      }
      return undefined;
    });
    return () => {
      active = false;
    };
  }, [config?.authConfigured, refreshSession, session?.token]);

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

  return { user: session, login, logout, refreshSession };
}
