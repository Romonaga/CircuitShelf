import { useEffect, useState } from "react";
import { AppShell } from "./components/AppShell";
import { AppViewRouter } from "./components/AppViewRouter";
import { LoginView } from "./components/LoginView";
import { useAppConfig } from "./hooks/useAppConfig";
import { useSession } from "./hooks/useSession";
import { useStatus } from "./hooks/useStatus";
import { useThemePreference } from "./hooks/useThemePreference";
import { ErrorMessage } from "./components/ErrorMessage";
import type { View } from "./types";
import { canAccessView, firstAccessibleView } from "./libs/viewAccess";

export default function App() {
  const [activeView, setActiveView] = useState<View>("ask");
  const [visitedViews, setVisitedViews] = useState<Set<View>>(() => new Set(["ask"]));
  const { config, error: configError } = useAppConfig();
  const { status, statusError, refreshStatus } = useStatus(
    config?.statusPollIntervalSeconds,
    config?.activeStatusPollIntervalSeconds
  );
  const { user, login, logout, refreshSession } = useSession(config);
  const { theme, setTheme, toggleTheme } = useThemePreference(Boolean(user));
  const error = configError || statusError;
  const viewAccess = {
    authenticated: Boolean(user),
    canManageEntity: Boolean(user?.entity?.canManage),
    canManageSystem: Boolean(user?.canManageSystem)
  };

  useEffect(() => {
    if (user?.forcePasswordChange) {
      setActiveView("account");
    }
  }, [user?.forcePasswordChange]);

  useEffect(() => {
    if (!user || user.forcePasswordChange) {
      return;
    }
    if (!canAccessView(activeView, viewAccess)) {
      setActiveView(firstAccessibleView(viewAccess));
    }
  }, [activeView, user, user?.forcePasswordChange, viewAccess.authenticated, viewAccess.canManageEntity, viewAccess.canManageSystem]);

  useEffect(() => {
    setVisitedViews((previous) => {
      if (previous.has(activeView)) {
        return previous;
      }
      const next = new Set(previous);
      next.add(activeView);
      return next;
    });
  }, [activeView]);

  const setGuardedActiveView = (view: View) => {
    if (user?.forcePasswordChange && view !== "account") {
      setActiveView("account");
      return;
    }
    if (!canAccessView(view, viewAccess)) {
      setActiveView(firstAccessibleView(viewAccess));
      return;
    }
    setActiveView(view);
  };

  if (!config) {
    return (
      <main className="loading-screen">
        <h1>CircuitShelf</h1>
        <p>{error || "Loading application settings..."}</p>
      </main>
    );
  }

  if (config.authConfigured && !user) {
    return <LoginView siteName={config.siteName} onLogin={login} />;
  }

  return (
    <AppShell
      activeView={activeView}
      setActiveView={setGuardedActiveView}
      siteName={config.siteName}
      user={user?.username || "local"}
      isAdmin={Boolean(user?.isAdmin)}
      canManageEntity={Boolean(user?.entity?.canManage)}
      canManageSystem={Boolean(user?.canManageSystem)}
      entityName={user?.entity?.name}
      entityRole={user?.entity?.roleName}
      status={status}
      theme={theme}
      onToggleTheme={toggleTheme}
      onLogout={logout}
    >
      <ErrorMessage message={error} className="top-error" />
      {user?.forcePasswordChange ? (
        <ErrorMessage
          className="top-error"
          message="Password change required before continuing with regular work."
        />
      ) : null}
      <AppViewRouter
        activeView={activeView}
        config={config}
        refreshSession={refreshSession}
        refreshStatus={refreshStatus}
        setActiveView={setGuardedActiveView}
        setTheme={setTheme}
        status={status}
        theme={theme}
        user={user}
        visitedViews={visitedViews}
      />
    </AppShell>
  );
}
