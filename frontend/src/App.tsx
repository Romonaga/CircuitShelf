import { lazy, Suspense, useEffect, useState } from "react";
import { AppShell } from "./components/AppShell";
import { AskView } from "./components/AskView";
import { LoginView } from "./components/LoginView";
import { LoadingSpinner } from "./components/LoadingSpinner";
import { useAppConfig } from "./hooks/useAppConfig";
import { useSession } from "./hooks/useSession";
import { useStatus } from "./hooks/useStatus";
import { useThemePreference } from "./hooks/useThemePreference";
import { ErrorMessage } from "./components/ErrorMessage";
import type { View } from "./types";
import { canAccessView, firstAccessibleView } from "./libs/viewAccess";

const AccountView = lazy(() => import("./components/AccountView").then((module) => ({ default: module.AccountView })));
const AIUsageView = lazy(() => import("./components/AIUsageView").then((module) => ({ default: module.AIUsageView })));
const BenchView = lazy(() => import("./components/BenchView").then((module) => ({ default: module.BenchView })));
const DocumentsView = lazy(() => import("./components/DocumentsView").then((module) => ({ default: module.DocumentsView })));
const EntitySettingsView = lazy(() => import("./components/EntitySettingsView").then((module) => ({ default: module.EntitySettingsView })));
const InventoryView = lazy(() => import("./components/InventoryView").then((module) => ({ default: module.InventoryView })));
const PerformanceView = lazy(() => import("./components/PerformanceView").then((module) => ({ default: module.PerformanceView })));
const ProjectFinderView = lazy(() => import("./components/ProjectFinderView").then((module) => ({ default: module.ProjectFinderView })));
const ReviewView = lazy(() => import("./components/ReviewView").then((module) => ({ default: module.ReviewView })));
const RuntimeCatalogView = lazy(() => import("./components/RuntimeCatalogView").then((module) => ({ default: module.RuntimeCatalogView })));
const SettingsView = lazy(() => import("./components/SettingsView").then((module) => ({ default: module.SettingsView })));
const StatusView = lazy(() => import("./components/StatusView").then((module) => ({ default: module.StatusView })));
const TraceView = lazy(() => import("./components/TraceView").then((module) => ({ default: module.TraceView })));

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
      <div hidden={activeView !== "ask"}>
        <AskView config={config} isActive={activeView === "ask"} />
      </div>
      <Suspense fallback={<main className="loading-screen compact"><LoadingSpinner /><p>Loading view...</p></main>}>
        {visitedViews.has("bench") ? (
          <div hidden={activeView !== "bench"}>
            <BenchView config={config} isActive={activeView === "bench"} />
          </div>
        ) : null}
        {visitedViews.has("finder") ? (
          <div hidden={activeView !== "finder"}>
            <ProjectFinderView config={config} isActive={activeView === "finder"} setActiveView={setGuardedActiveView} />
          </div>
        ) : null}
        {visitedViews.has("inventory") ? (
          <div hidden={activeView !== "inventory"}>
            <InventoryView isActive={activeView === "inventory"} />
          </div>
        ) : null}
        {(user?.entity?.canManage || user?.canManageSystem) && visitedViews.has("entity") ? (
          <div hidden={activeView !== "entity"}>
            <EntitySettingsView entity={user?.entity} canManage={Boolean(user?.entity?.canManage)} />
          </div>
        ) : null}
        {visitedViews.has("documents") ? (
          <div hidden={activeView !== "documents"}>
            <DocumentsView
              isActive={activeView === "documents"}
              isAdmin={Boolean(user?.entity?.canManage || user?.canManageSystem)}
              status={status}
              refreshSignal={`${status?.sources ?? 0}:${status?.chunks ?? 0}:${status?.imageIds ?? 0}`}
              onStatusChange={refreshStatus}
              onOpenReview={() => setGuardedActiveView("review")}
            />
          </div>
        ) : null}
        {user?.canManageSystem && visitedViews.has("corpus") ? (
          <div hidden={activeView !== "corpus"}>
            <DocumentsView
              isActive={activeView === "corpus"}
              isAdmin={Boolean(user?.canManageSystem)}
              status={status}
              refreshSignal={`${status?.sources ?? 0}:${status?.chunks ?? 0}:${status?.imageIds ?? 0}`}
              onStatusChange={refreshStatus}
              onOpenReview={() => setGuardedActiveView("review")}
              title="Corpus"
              description={`${status?.sources ?? 0} global indexed sources`}
              uploadHelp="Upload shared electronics books, datasheets, and notes for the global CircuitShelf corpus."
              emptyText="Select a corpus document to inspect its pages, chunks, images, and pinout."
              scope="global"
            />
          </div>
        ) : null}
        {(user?.entity?.canManage || user?.canManageSystem) && visitedViews.has("review") ? (
          <div hidden={activeView !== "review"}>
            <ReviewView
              canManageSystem={Boolean(user?.canManageSystem)}
              isActive={activeView === "review"}
              refreshSignal={status?.pendingReview ?? 0}
              onStatusChange={refreshStatus}
            />
          </div>
        ) : null}
        {visitedViews.has("trace") ? (
          <div hidden={activeView !== "trace"}>
            <TraceView isActive={activeView === "trace"} isAdmin={Boolean(user?.isAdmin)} />
          </div>
        ) : null}
        {visitedViews.has("status") ? (
          <div hidden={activeView !== "status"}>
            <StatusView status={status} refresh={refreshStatus} isActive={activeView === "status"} isAdmin={Boolean(user?.isAdmin)} />
          </div>
        ) : null}
        {visitedViews.has("performance") ? (
          <div hidden={activeView !== "performance"}>
            <PerformanceView
              status={status}
              isActive={activeView === "performance"}
              onOpenReview={() => setGuardedActiveView("review")}
            />
          </div>
        ) : null}
        {visitedViews.has("aiUsage") ? (
          <div hidden={activeView !== "aiUsage"}>
            <AIUsageView
              isActive={activeView === "aiUsage"}
              canManageEntity={Boolean(user?.entity?.canManage)}
              canManageSystem={Boolean(user?.canManageSystem)}
            />
          </div>
        ) : null}
        {visitedViews.has("account") ? (
          <div hidden={activeView !== "account"}>
            <AccountView username={user?.username || "local"} config={config} theme={theme} setTheme={setTheme} onPasswordChanged={refreshSession} />
          </div>
        ) : null}
        {user?.canManageSystem && visitedViews.has("settings") ? (
          <div hidden={activeView !== "settings"}>
            <SettingsView />
          </div>
        ) : null}
        {user?.canManageSystem && visitedViews.has("runtime") ? (
          <div hidden={activeView !== "runtime"}>
            <RuntimeCatalogView isActive={activeView === "runtime"} />
          </div>
        ) : null}
      </Suspense>
    </AppShell>
  );
}
