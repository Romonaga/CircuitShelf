import { Suspense } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { ThemeMode } from "../hooks/useThemePreference";
import type { AppConfig, SessionUser, StatusPayload, View } from "../types";
import { AskView } from "./AskView";
import {
  AccountView,
  AIUsageView,
  BenchView,
  DocumentsView,
  EntitySettingsView,
  InventoryView,
  PerformanceView,
  ProjectFinderView,
  ReviewView,
  RuntimeCatalogView,
  SettingsView,
  StatusView,
  TraceView,
} from "./app/LazyViews";
import { ViewPane } from "./app/ViewPane";
import { LoadingSpinner } from "./LoadingSpinner";

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
      <ViewPane activeView={activeView} view="ask" mounted>
        <AskView config={config} isActive={activeView === "ask"} />
      </ViewPane>
      <Suspense fallback={<main className="loading-screen compact"><LoadingSpinner /><p>Loading view...</p></main>}>
        <ViewPane activeView={activeView} view="bench" mounted={visitedViews.has("bench")}>
          <BenchView config={config} isActive={activeView === "bench"} />
        </ViewPane>
        <ViewPane activeView={activeView} view="finder" mounted={visitedViews.has("finder")}>
          <ProjectFinderView config={config} isActive={activeView === "finder"} setActiveView={setActiveView} />
        </ViewPane>
        <ViewPane activeView={activeView} view="inventory" mounted={visitedViews.has("inventory")}>
          <InventoryView isActive={activeView === "inventory"} />
        </ViewPane>
        <ViewPane activeView={activeView} view="entity" mounted={(canManageEntity || canManageSystem) && visitedViews.has("entity")}>
          <EntitySettingsView entity={user?.entity} canManage={canManageEntity} />
        </ViewPane>
        <ViewPane activeView={activeView} view="documents" mounted={visitedViews.has("documents")}>
          <DocumentsView
            isActive={activeView === "documents"}
            isAdmin={canManageEntity || canManageSystem}
            status={status}
            refreshSignal={documentRefreshSignal}
            onStatusChange={refreshStatus}
            onOpenReview={() => setActiveView("review")}
          />
        </ViewPane>
        <ViewPane activeView={activeView} view="corpus" mounted={canManageSystem && visitedViews.has("corpus")}>
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
        </ViewPane>
        <ViewPane activeView={activeView} view="review" mounted={(canManageEntity || canManageSystem) && visitedViews.has("review")}>
          <ReviewView
            canManageSystem={canManageSystem}
            isActive={activeView === "review"}
            refreshSignal={status?.pendingReview ?? 0}
            onStatusChange={refreshStatus}
          />
        </ViewPane>
        <ViewPane activeView={activeView} view="trace" mounted={visitedViews.has("trace")}>
          <TraceView isActive={activeView === "trace"} isAdmin={isAdmin} />
        </ViewPane>
        <ViewPane activeView={activeView} view="status" mounted={visitedViews.has("status")}>
          <StatusView status={status} refresh={refreshStatus} isActive={activeView === "status"} isAdmin={isAdmin} />
        </ViewPane>
        <ViewPane activeView={activeView} view="performance" mounted={visitedViews.has("performance")}>
          <PerformanceView
            status={status}
            isActive={activeView === "performance"}
            onOpenReview={() => setActiveView("review")}
          />
        </ViewPane>
        <ViewPane activeView={activeView} view="aiUsage" mounted={visitedViews.has("aiUsage")}>
          <AIUsageView
            isActive={activeView === "aiUsage"}
            canManageEntity={canManageEntity}
            canManageSystem={canManageSystem}
          />
        </ViewPane>
        <ViewPane activeView={activeView} view="account" mounted={visitedViews.has("account")}>
          <AccountView username={user?.username || "local"} config={config} theme={theme} setTheme={setTheme} onPasswordChanged={refreshSession} />
        </ViewPane>
        <ViewPane activeView={activeView} view="settings" mounted={canManageSystem && visitedViews.has("settings")}>
          <SettingsView />
        </ViewPane>
        <ViewPane activeView={activeView} view="runtime" mounted={canManageSystem && visitedViews.has("runtime")}>
          <RuntimeCatalogView isActive={activeView === "runtime"} />
        </ViewPane>
      </Suspense>
    </>
  );
}
