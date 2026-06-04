import { ReactNode } from "react";

export function CollapsibleSection({
  title,
  description,
  collapsed,
  onToggle,
  actions,
  children
}: {
  title: string;
  description?: string;
  collapsed: boolean;
  onToggle: () => void;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className={collapsed ? "collapsible-section collapsed" : "collapsible-section"}>
      <header className="collapsible-section-header">
        <button className="collapsible-section-toggle" type="button" onClick={onToggle} aria-expanded={!collapsed}>
          <span className="collapse-caret" aria-hidden="true">{collapsed ? ">" : "v"}</span>
          <span>
            <strong>{title}</strong>
            {description ? <small>{description}</small> : null}
          </span>
        </button>
        {actions ? <div className="collapsible-section-actions">{actions}</div> : null}
      </header>
      {collapsed ? null : <div className="collapsible-section-body">{children}</div>}
    </section>
  );
}
