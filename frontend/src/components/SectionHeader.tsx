import { ReactNode } from "react";

export function SectionHeader({
  title,
  description,
  actions
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className={actions ? "section-heading inline-heading" : "section-heading"}>
      <div>
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {actions}
    </div>
  );
}
