import { ReactNode } from "react";
import type { StatusPayload, View } from "../types";
import { formatNumber } from "../lib/format";
import type { ThemeMode } from "../hooks/useThemePreference";
import { LogoMark } from "./LogoMark";
import { Stat } from "./Stat";

export function AppShell({
  activeView,
  setActiveView,
  siteName,
  user,
  isAdmin,
  canManageSystem,
  entityName,
  entityRole,
  status,
  theme,
  onToggleTheme,
  onRefresh,
  onLogout,
  children
}: {
  activeView: View;
  setActiveView: (view: View) => void;
  siteName: string;
  user: string;
  isAdmin: boolean;
  canManageSystem: boolean;
  entityName?: string | null;
  entityRole?: string | null;
  status: StatusPayload | null;
  theme: ThemeMode;
  onToggleTheme: () => void;
  onRefresh: () => void;
  onLogout: () => void;
  children: ReactNode;
}) {
  const viewLabels: Record<View, string> = {
    ask: "Ask",
    bench: "Bench",
    finder: "Finder",
    inventory: "Inventory",
    documents: "Documents",
    corpus: "Corpus",
    review: "Review",
    trace: "Trace",
    status: "Status",
    settings: "Admin Settings",
    entity: "Entity",
    account: "Account"
  };
  const navGroups: Array<{ label: string; items: Array<{ id: View; label: string }> }> = [
    {
      label: "Workbench",
      items: [
        { id: "ask", label: "Ask" },
        { id: "bench", label: "Bench" },
        { id: "finder", label: "Finder" }
      ]
    },
    {
      label: "Lab",
      items: [
        { id: "inventory", label: "Inventory" },
        { id: "documents", label: "Documents" },
        { id: "entity", label: "Entity" }
      ]
    },
    {
      label: "System",
      items: [
        { id: "trace" as View, label: "Trace" },
        { id: "status" as View, label: "Status" }
      ]
    },
    ...(isAdmin || canManageSystem
      ? [{
      label: "Admin",
      items: [
        ...(canManageSystem ? [{ id: "corpus" as View, label: "Corpus" }] : []),
        ...(isAdmin ? [{ id: "review" as View, label: `Review${status?.pendingReview ? ` (${status.pendingReview})` : ""}` }] : []),
        ...(canManageSystem ? [{ id: "settings" as View, label: "System Settings" }] : [])
      ]
    }]
      : [])
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <LogoMark />
          <div>
            <h1>{siteName}</h1>
            <p>{user}</p>
            {entityName ? <p className="brand-entity">{entityName} · {entityRole}</p> : null}
          </div>
        </div>
        <nav>
          {navGroups.map((group) => (
            <section key={group.label} className="nav-group">
              <p className="nav-group-label">{group.label}</p>
              {group.items.map((item) => (
                <button
                  key={item.id}
                  className={activeView === item.id ? "nav-item active" : "nav-item"}
                  onClick={() => setActiveView(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </section>
          ))}
        </nav>
        <div className="sidebar-footer">
          <Stat label="Chunks" value={formatNumber(status?.chunks)} />
          <Stat label="Sources" value={formatNumber(status?.sources)} />
          <button className="ghost-button" onClick={onRefresh}>
            Refresh
          </button>
          <button className="ghost-button" onClick={() => setActiveView("account")}>
            Account
          </button>
          <button className="ghost-button" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="workspace">
        <div className="workspace-topbar">
          <div>
            <span>{viewLabels[activeView]}</span>
            <strong>{siteName}</strong>
          </div>
          <button className="ghost-button theme-button" onClick={onToggleTheme}>
            {theme === "dark" ? "Light bench" : "Dark bench"}
          </button>
        </div>
        <div className="workspace-body">{children}</div>
      </main>
    </div>
  );
}
