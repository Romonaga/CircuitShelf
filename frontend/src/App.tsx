import { useState } from "react";
import { AppShell } from "./components/AppShell";
import { AskView } from "./components/AskView";
import { DocumentsView } from "./components/DocumentsView";
import { LoginView } from "./components/LoginView";
import { StatusView } from "./components/StatusView";
import { TraceView } from "./components/TraceView";
import { useAppConfig } from "./hooks/useAppConfig";
import { useSession } from "./hooks/useSession";
import { useStatus } from "./hooks/useStatus";
import { ErrorMessage } from "./components/ErrorMessage";
import type { View } from "./types";

export default function App() {
  const [activeView, setActiveView] = useState<View>("ask");
  const { config, error: configError } = useAppConfig();
  const { status, statusError, refreshStatus } = useStatus();
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
      user={user || "local"}
      status={status}
      onRefresh={refreshStatus}
      onLogout={logout}
    >
      <ErrorMessage message={error} className="top-error" />
      {activeView === "ask" ? <AskView config={config} /> : null}
      {activeView === "documents" ? <DocumentsView /> : null}
      {activeView === "trace" ? <TraceView /> : null}
      {activeView === "status" ? <StatusView status={status} refresh={refreshStatus} /> : null}
    </AppShell>
  );
}
