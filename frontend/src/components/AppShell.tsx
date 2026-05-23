import { ReactNode } from "react";
import type { StatusPayload, View } from "../types";
import { formatNumber } from "../lib/format";
import { Stat } from "./Stat";

export function AppShell({
  activeView,
  setActiveView,
  siteName,
  user,
  isAdmin,
  status,
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
  onRefresh: () => void;
  onLogout: () => void;
  children: ReactNode;
}) {
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
    {
      label: "System",
      items: [
        ...(isAdmin ? [{ id: "review" as View, label: `Review${status?.pendingReview ? ` (${status.pendingReview})` : ""}` }] : []),
        { id: "trace", label: "Trace" },
        { id: "status", label: "Status" },
        ...(isAdmin ? [{ id: "settings" as View, label: "Settings" }] : [])
      ]
    }
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">CS</div>
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
          <button className="ghost-button" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="workspace">{children}</main>
    </div>
  );
}
