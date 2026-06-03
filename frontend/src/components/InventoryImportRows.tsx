import type { InventoryImportItem, InventoryLocation } from "../types";

const partTypes = ["component", "ic", "resistor", "capacitor", "diode", "transistor", "sensor", "module", "board", "display", "tooling", "power"];

export function InventoryImportRows({
  items,
  locations,
  onUpdate
}: {
  items: InventoryImportItem[];
  locations: InventoryLocation[];
  onUpdate: (index: number, patch: Partial<InventoryImportItem>) => void;
}) {
  if (!items.length) {
    return null;
  }
  return (
    <div className="inventory-import-list">
      {items.map((item, index) => (
        <article key={`${item.rawLine}-${index}`} className="inventory-import-row">
          <label className="check-row">
            <input type="checkbox" checked={Boolean(item.selected)} onChange={(event) => onUpdate(index, { selected: event.target.checked })} />
            {item.action === "merge" ? "Add to existing stock" : "Create new part"}
          </label>
          <div className="inventory-import-fields">
            <input value={item.displayName} onChange={(event) => onUpdate(index, { displayName: event.target.value })} />
            <select value={item.partType} onChange={(event) => onUpdate(index, { partType: event.target.value })}>
              {partTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
            <input type="number" min="0" value={item.quantity} onChange={(event) => onUpdate(index, { quantity: Number(event.target.value) })} />
            <select
              value={item.locationId || ""}
              onChange={(event) => {
                const location = locations.find((candidate) => candidate.id === event.target.value);
                onUpdate(index, { locationId: location?.id || null, location: location?.displayName || "" });
              }}
            >
              <option value="">Unsorted</option>
              {locations.map((location) => (
                <option key={location.id} value={location.id}>
                  {location.displayName}
                </option>
              ))}
            </select>
          </div>
          <small>From: {item.rawLine}</small>
          <small>Aliases: {item.aliases.join(", ") || "none"}</small>
          {item.warnings.length ? (
            <div className="inventory-import-warnings">
              {item.warnings.map((warning) => (
                <span key={warning}>{warning}</span>
              ))}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}
