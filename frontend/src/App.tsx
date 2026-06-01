import { useEffect, useState } from "react";
import { AccountView } from "./components/AccountView";
import { AIUsageView } from "./components/AIUsageView";
import { AppShell } from "./components/AppShell";
import { AskView } from "./components/AskView";
import { BenchView } from "./components/BenchView";
import { DocumentsView } from "./components/DocumentsView";
import { InventoryView } from "./components/InventoryView";
import { LoginView } from "./components/LoginView";
import { ProjectFinderView } from "./components/ProjectFinderView";
import { PerformanceView } from "./components/PerformanceView";
import { ReviewView } from "./components/ReviewView";
import { RuntimeCatalogView } from "./components/RuntimeCatalogView";
import { StatusView } from "./components/StatusView";
import { SettingsView } from "./components/SettingsView";
import { TraceView } from "./components/TraceView";
import { useAppConfig } from "./hooks/useAppConfig";
import { useSession } from "./hooks/useSession";
import { useStatus } from "./hooks/useStatus";
import { useThemePreference } from "./hooks/useThemePreference";
import { ErrorMessage } from "./components/ErrorMessage";
import { EntitySettingsView } from "./components/EntitySettingsView";
import type { View } from "./types";

export default function App() {
  const [activeView, setActiveView] = useState<View>("ask");
  const { config, error: configError } = useAppConfig();
  const { status, statusError, refreshStatus } = useStatus(
    config?.statusPollIntervalSeconds,
    config?.activeStatusPollIntervalSeconds
  );
  const { user, login, logout, refreshSession } = useSession(config);
  const { theme, setTheme, toggleTheme } = useThemePreference(Boolean(user));
  const error = configError || statusError;

  useEffect(() => {
    if (user?.forcePasswordChange) {
      setActiveView("account");
    }
  }, [user?.forcePasswordChange]);

  const setGuardedActiveView = (view: View) => {
    if (user?.forcePasswordChange && view !== "account") {
      setActiveView("account");
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
        <AskView config={config} />
      </div>
      <div hidden={activeView !== "bench"}>
        <BenchView config={config} isActive={activeView === "bench"} />
      </div>
      <div hidden={activeView !== "finder"}>
        <ProjectFinderView config={config} isActive={activeView === "finder"} setActiveView={setGuardedActiveView} />
      </div>
      <div hidden={activeView !== "inventory"}>
        <InventoryView isActive={activeView === "inventory"} />
      </div>
      <div hidden={activeView !== "entity"}>
        <EntitySettingsView entity={user?.entity} canManage={Boolean(user?.entity?.canManage)} />
      </div>
      <div hidden={activeView !== "documents"}>
        <DocumentsView
          isActive={activeView === "documents"}
          isAdmin={Boolean(user?.isAdmin)}
          status={status}
          refreshSignal={`${status?.sources ?? 0}:${status?.chunks ?? 0}:${status?.imageIds ?? 0}`}
          onStatusChange={refreshStatus}
          onOpenReview={() => setGuardedActiveView("review")}
        />
      </div>
      {user?.canManageSystem ? (
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
      {user?.isAdmin ? (
        <div hidden={activeView !== "review"}>
          <ReviewView
            canManageSystem={Boolean(user?.canManageSystem)}
            isActive={activeView === "review"}
            refreshSignal={status?.pendingReview ?? 0}
            onStatusChange={refreshStatus}
          />
        </div>
      ) : null}
      <div hidden={activeView !== "trace"}>
        <TraceView />
      </div>
      <div hidden={activeView !== "status"}>
        <StatusView status={status} refresh={refreshStatus} isActive={activeView === "status"} isAdmin={Boolean(user?.isAdmin)} />
      </div>
      <div hidden={activeView !== "performance"}>
        <PerformanceView
          status={status}
          refresh={refreshStatus}
          isActive={activeView === "performance"}
          onOpenReview={() => setGuardedActiveView("review")}
        />
      </div>
      <div hidden={activeView !== "aiUsage"}>
        <AIUsageView
          isActive={activeView === "aiUsage"}
          canManageEntity={Boolean(user?.entity?.canManage)}
          canManageSystem={Boolean(user?.canManageSystem)}
        />
      </div>
      <div hidden={activeView !== "account"}>
        <AccountView username={user?.username || "local"} theme={theme} setTheme={setTheme} onPasswordChanged={refreshSession} />
      </div>
      {user?.canManageSystem ? (
        <div hidden={activeView !== "settings"}>
          <SettingsView />
        </div>
      ) : null}
      {user?.canManageSystem ? (
        <div hidden={activeView !== "runtime"}>
          <RuntimeCatalogView isActive={activeView === "runtime"} />
        </div>
      ) : null}
    </AppShell>
  );
}
