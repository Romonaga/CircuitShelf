import { ReactNode, useState } from "react";
import type { StatusPayload, View } from "../types";
import { formatNumber } from "../libs/format";
import type { ThemeMode } from "../hooks/useThemePreference";
import { LogoMark } from "./LogoMark";
import { Stat } from "./Stat";
import { SidebarSystemCard } from "./SidebarSystemCard";
import { canAccessView } from "../libs/viewAccess";

export function AppShell({
  activeView,
  setActiveView,
  siteName,
  user,
  isAdmin,
  canManageEntity,
  canManageSystem,
  entityName,
  entityRole,
  status,
  theme,
  onToggleTheme,
  onLogout,
  children
}: {
  activeView: View;
  setActiveView: (view: View) => void;
  siteName: string;
  user: string;
  isAdmin: boolean;
  canManageEntity: boolean;
  canManageSystem: boolean;
  entityName?: string | null;
  entityRole?: string | null;
  status: StatusPayload | null;
  theme: ThemeMode;
  onToggleTheme: () => void;
  onLogout: () => void;
  children: ReactNode;
}) {
  const [monitorMode, setMonitorMode] = useState(false);
  type NavItem = { id: View; label: string };
  type NavGroup = { label: string; items: NavItem[] };
  const access = {
    authenticated: true,
    canManageEntity,
    canManageSystem
  };
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
    performance: "Performance",
    work: "Work",
    aiUsage: "AI Usage",
    settings: "Admin Settings",
    runtime: "Runtime Catalog",
    entity: "Entity",
    account: "Account"
  };
  const navGroups: NavGroup[] = [
    {
      label: "Workbench",
      items: [
        { id: "ask" as View, label: "Ask" },
        { id: "bench" as View, label: "Bench" },
        { id: "finder" as View, label: "Finder" }
      ]
    },
    {
      label: "Lab",
      items: [
        { id: "inventory" as View, label: "Inventory" },
        { id: "documents" as View, label: "Documents" },
        { id: "entity" as View, label: "Entity" }
      ]
    },
    {
      label: "System",
      items: [
        { id: "trace" as View, label: "Trace" },
        { id: "status" as View, label: "Status" },
        { id: "performance" as View, label: "Performance" },
        { id: "work" as View, label: "Work" },
        { id: "aiUsage" as View, label: "AI Usage" }
      ]
    },
    ...(isAdmin || canManageEntity || canManageSystem
      ? [{
      label: "Admin",
      items: [
        ...(canManageSystem ? [{ id: "corpus" as View, label: "Corpus" }] : []),
        ...(isAdmin || canManageEntity || canManageSystem ? [{ id: "review" as View, label: `Review${status?.pendingReview ? ` (${status.pendingReview})` : ""}` }] : []),
        ...(canManageSystem ? [
          { id: "settings" as View, label: "System Settings" },
          { id: "runtime" as View, label: "Runtime Catalog" }
        ] : [])
      ]
    }]
      : [])
  ]
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => canAccessView(item.id, access))
    }))
    .filter((group) => group.items.length > 0);

  return (
    <div className={monitorMode ? "app-shell sidebar-monitor-mode" : "app-shell"}>
      <aside className="sidebar">
        <div className="brand-block">
          <LogoMark />
          <div>
            <h1>{siteName}</h1>
            <p>{user}</p>
            {entityName ? <p className="brand-entity">{entityName} · {entityRole}</p> : null}
            <div className="brand-actions">
              <button type="button" onClick={() => setActiveView("account")}>Account</button>
              <button type="button" onClick={() => setMonitorMode((value) => !value)}>
                {monitorMode ? "Full menu" : "Monitor"}
              </button>
              <button type="button" onClick={onLogout}>Sign out</button>
            </div>
          </div>
        </div>
        <nav className="sidebar-nav">
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
          <SidebarSystemCard status={status} detailed={monitorMode} />
          {!monitorMode ? (
            <>
              <Stat label="Chunks" value={formatNumber(status?.chunks)} />
              <Stat label="Sources" value={formatNumber(status?.sources)} />
            </>
          ) : null}
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
