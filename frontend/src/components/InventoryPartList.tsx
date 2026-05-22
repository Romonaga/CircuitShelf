import type { InventoryPart } from "../types";
import { formatNumber } from "../lib/format";

export function InventoryPartList({
  parts,
  loading,
  onRemove
}: {
  parts: InventoryPart[];
  loading: boolean;
  onRemove: (partId: string) => void;
}) {
  if (loading && !parts.length) {
    return <div className="empty-state compact">Loading inventory...</div>;
  }

  if (!parts.length) {
    return <div className="empty-state compact">No lab parts stored yet.</div>;
  }

  return (
    <div className="inventory-part-list">
      {parts.map((part) => (
        <article key={part.id} className="inventory-part-row">
          <div>
            <strong>{part.displayName}</strong>
            <small>
              {part.partType} | Qty {formatNumber(part.quantity)}
              {part.location ? ` | ${part.location}` : ""}
            </small>
            {part.aliases.length ? <small>Aliases: {part.aliases.join(", ")}</small> : null}
          </div>
          <button className="ghost-button danger-button compact-button" type="button" onClick={() => onRemove(part.id)}>
            Remove
          </button>
        </article>
      ))}
    </div>
  );
}
