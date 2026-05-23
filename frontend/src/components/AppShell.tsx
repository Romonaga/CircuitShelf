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
    review: "Review",
    trace: "Trace",
    status: "Status",
    settings: "Admin Settings",
    account: "Account"
  };
  const navGroups: Array<{ label: string; items: Array<{ id: View; label: string }> }> = [
    {
      label: "Build",
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
        { id: "documents", label: "Documents" }
      ]
    },
    ...(isAdmin
      ? [{
      label: "Admin",
      items: [
        { id: "review" as View, label: `Review${status?.pendingReview ? ` (${status.pendingReview})` : ""}` },
        { id: "trace" as View, label: "Trace" },
        { id: "status" as View, label: "Status" },
        { id: "settings" as View, label: "Settings" }
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
