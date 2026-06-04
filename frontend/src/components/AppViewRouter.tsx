import { lazy, Suspense } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { ThemeMode } from "../hooks/useThemePreference";
import type { AppConfig, SessionUser, StatusPayload, View } from "../types";
import { AskView } from "./AskView";
import { LoadingSpinner } from "./LoadingSpinner";

const AccountView = lazy(() => import("./AccountView").then((module) => ({ default: module.AccountView })));
const AIUsageView = lazy(() => import("./AIUsageView").then((module) => ({ default: module.AIUsageView })));
const BenchView = lazy(() => import("./BenchView").then((module) => ({ default: module.BenchView })));
const DocumentsView = lazy(() => import("./DocumentsView").then((module) => ({ default: module.DocumentsView })));
const EntitySettingsView = lazy(() => import("./EntitySettingsView").then((module) => ({ default: module.EntitySettingsView })));
const InventoryView = lazy(() => import("./InventoryView").then((module) => ({ default: module.InventoryView })));
const PerformanceView = lazy(() => import("./PerformanceView").then((module) => ({ default: module.PerformanceView })));
const ProjectFinderView = lazy(() => import("./ProjectFinderView").then((module) => ({ default: module.ProjectFinderView })));
const ReviewView = lazy(() => import("./ReviewView").then((module) => ({ default: module.ReviewView })));
const RuntimeCatalogView = lazy(() => import("./RuntimeCatalogView").then((module) => ({ default: module.RuntimeCatalogView })));
const SettingsView = lazy(() => import("./SettingsView").then((module) => ({ default: module.SettingsView })));
const StatusView = lazy(() => import("./StatusView").then((module) => ({ default: module.StatusView })));
const TraceView = lazy(() => import("./TraceView").then((module) => ({ default: module.TraceView })));

export function AppViewRouter({
  activeView,
  config,
  refreshSession,
  refreshStatus,
  setActiveView,
  setTheme,
  status,
  theme,
  user,
  visitedViews
}: {
  activeView: View;
  config: AppConfig;
  refreshSession: () => void;
  refreshStatus: () => void;
  setActiveView: (view: View) => void;
  setTheme: Dispatch<SetStateAction<ThemeMode>>;
  status: StatusPayload | null;
  theme: ThemeMode;
  user: SessionUser | null;
  visitedViews: Set<View>;
}) {
  const canManageEntity = Boolean(user?.entity?.canManage);
  const canManageSystem = Boolean(user?.canManageSystem);
  const isAdmin = Boolean(user?.isAdmin);
  const documentRefreshSignal = `${status?.sources ?? 0}:${status?.chunks ?? 0}:${status?.imageIds ?? 0}`;

  return (
    <>
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
            <ProjectFinderView config={config} isActive={activeView === "finder"} setActiveView={setActiveView} />
          </div>
        ) : null}
        {visitedViews.has("inventory") ? (
          <div hidden={activeView !== "inventory"}>
            <InventoryView isActive={activeView === "inventory"} />
          </div>
        ) : null}
        {(canManageEntity || canManageSystem) && visitedViews.has("entity") ? (
          <div hidden={activeView !== "entity"}>
            <EntitySettingsView entity={user?.entity} canManage={canManageEntity} />
          </div>
        ) : null}
        {visitedViews.has("documents") ? (
          <div hidden={activeView !== "documents"}>
            <DocumentsView
              isActive={activeView === "documents"}
              isAdmin={canManageEntity || canManageSystem}
              status={status}
              refreshSignal={documentRefreshSignal}
              onStatusChange={refreshStatus}
              onOpenReview={() => setActiveView("review")}
            />
          </div>
        ) : null}
        {canManageSystem && visitedViews.has("corpus") ? (
          <div hidden={activeView !== "corpus"}>
            <DocumentsView
              isActive={activeView === "corpus"}
              isAdmin={canManageSystem}
              status={status}
              refreshSignal={documentRefreshSignal}
              onStatusChange={refreshStatus}
              onOpenReview={() => setActiveView("review")}
              title="Corpus"
              description={`${status?.sources ?? 0} global indexed sources`}
              uploadHelp="Upload shared electronics books, datasheets, and notes for the global CircuitShelf corpus."
              emptyText="Select a corpus document to inspect its pages, chunks, images, and pinout."
              scope="global"
            />
          </div>
        ) : null}
        {(canManageEntity || canManageSystem) && visitedViews.has("review") ? (
          <div hidden={activeView !== "review"}>
            <ReviewView
              canManageSystem={canManageSystem}
              isActive={activeView === "review"}
              refreshSignal={status?.pendingReview ?? 0}
              onStatusChange={refreshStatus}
            />
          </div>
        ) : null}
        {visitedViews.has("trace") ? (
          <div hidden={activeView !== "trace"}>
            <TraceView isActive={activeView === "trace"} isAdmin={isAdmin} />
          </div>
        ) : null}
        {visitedViews.has("status") ? (
          <div hidden={activeView !== "status"}>
            <StatusView status={status} refresh={refreshStatus} isActive={activeView === "status"} isAdmin={isAdmin} />
          </div>
        ) : null}
        {visitedViews.has("performance") ? (
          <div hidden={activeView !== "performance"}>
            <PerformanceView
              status={status}
              isActive={activeView === "performance"}
              onOpenReview={() => setActiveView("review")}
            />
          </div>
        ) : null}
        {visitedViews.has("aiUsage") ? (
          <div hidden={activeView !== "aiUsage"}>
            <AIUsageView
              isActive={activeView === "aiUsage"}
              canManageEntity={canManageEntity}
              canManageSystem={canManageSystem}
            />
          </div>
        ) : null}
        {visitedViews.has("account") ? (
          <div hidden={activeView !== "account"}>
            <AccountView username={user?.username || "local"} config={config} theme={theme} setTheme={setTheme} onPasswordChanged={refreshSession} />
          </div>
        ) : null}
        {canManageSystem && visitedViews.has("settings") ? (
          <div hidden={activeView !== "settings"}>
            <SettingsView />
          </div>
        ) : null}
        {canManageSystem && visitedViews.has("runtime") ? (
          <div hidden={activeView !== "runtime"}>
            <RuntimeCatalogView isActive={activeView === "runtime"} />
          </div>
        ) : null}
      </Suspense>
    </>
  );
}
