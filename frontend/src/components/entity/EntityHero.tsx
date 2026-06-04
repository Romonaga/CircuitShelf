import type { EntityContext } from "../../types";
import { SectionHeader } from "../SectionHeader";

export function EntityHero({ entity, canManage }: { entity: EntityContext; canManage: boolean }) {
  return (
    <div className="entity-hero">
      <SectionHeader title={entity.name} description={`${entity.roleName} access`} />
      <div className="entity-stat-row">
        <span>Slug: {entity.slug}</span>
        <span>{canManage ? "Entity management enabled" : "Read-only membership"}</span>
      </div>
    </div>
  );
}
