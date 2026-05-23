import { useState } from "react";
import { AppShell } from "./components/AppShell";
import { AskView } from "./components/AskView";
import { BenchView } from "./components/BenchView";
import { DocumentsView } from "./components/DocumentsView";
import { InventoryView } from "./components/InventoryView";
import { LoginView } from "./components/LoginView";
import { ProjectFinderView } from "./components/ProjectFinderView";
import { ReviewView } from "./components/ReviewView";
import { StatusView } from "./components/StatusView";
import { SettingsView } from "./components/SettingsView";
import { TraceView } from "./components/TraceView";
import { useAppConfig } from "./hooks/useAppConfig";
import { useSession } from "./hooks/useSession";
import { useStatus } from "./hooks/useStatus";
import { ErrorMessage } from "./components/ErrorMessage";
import type { View } from "./types";

export default function App() {
  const [activeView, setActiveView] = useState<View>("ask");
  const { config, error: configError } = useAppConfig();
  const { status, statusError, refreshStatus } = useStatus(
    config?.statusPollIntervalSeconds,
    config?.activeStatusPollIntervalSeconds
  );
  const { user, login, logout } = useSession(config);
  const error = configError || statusError;

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
      setActiveView={setActiveView}
      siteName={config.siteName}
      user={user?.username || "local"}
      isAdmin={Boolean(user?.isAdmin)}
      status={status}
      onRefresh={refreshStatus}
      onLogout={logout}
    >
      <ErrorMessage message={error} className="top-error" />
      <div hidden={activeView !== "ask"}>
        <AskView config={config} />
      </div>
      <div hidden={activeView !== "bench"}>
        <BenchView config={config} isActive={activeView === "bench"} />
      </div>
      <div hidden={activeView !== "finder"}>
        <ProjectFinderView config={config} isActive={activeView === "finder"} setActiveView={setActiveView} />
      </div>
      <div hidden={activeView !== "inventory"}>
        <InventoryView isActive={activeView === "inventory"} />
      </div>
      <div hidden={activeView !== "documents"}>
        <DocumentsView
          isActive={activeView === "documents"}
          isAdmin={Boolean(user?.isAdmin)}
          status={status}
          refreshSignal={`${status?.sources ?? 0}:${status?.chunks ?? 0}:${status?.imageIds ?? 0}`}
          onStatusChange={refreshStatus}
          onOpenReview={() => setActiveView("review")}
        />
      </div>
      {user?.isAdmin ? (
        <div hidden={activeView !== "review"}>
          <ReviewView
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
      {user?.isAdmin ? (
        <div hidden={activeView !== "settings"}>
          <SettingsView />
        </div>
      ) : null}
    </AppShell>
  );
}
