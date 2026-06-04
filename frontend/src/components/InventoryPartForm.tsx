import type { InventoryLocation, InventoryPart, InventoryPartInput } from "../types";
import { useInventoryPartDraft } from "../hooks/inventory/useInventoryPartDraft";
import { inventoryPartTypes } from "../libs/inventory/partDraft";

export function InventoryPartForm({
  saving,
  editingPart,
  locations,
  onCancel,
  onSave
}: {
  saving: boolean;
  editingPart?: InventoryPart | null;
  locations: InventoryLocation[];
  onCancel?: () => void;
  onSave: (part: InventoryPartInput) => Promise<boolean>;
}) {
  const draft = useInventoryPartDraft({ editingPart, locations, onSave });
  const part = draft.part;

  return (
    <form className="inventory-part-form" onSubmit={(event) => void draft.submit(event)}>
      <label>
        Part
        <input
          value={part.displayName}
          onChange={(event) => draft.setPart({ ...part, displayName: event.target.value })}
          placeholder="NE555, 10 kOhm resistor, Arduino Uno"
        />
      </label>
      <div className="inventory-form-grid">
        <label>
          Type
          <select value={part.partType} onChange={(event) => draft.setPart({ ...part, partType: event.target.value })}>
            {inventoryPartTypes.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          Qty
          <input
            type="number"
            min="0"
            value={part.quantity}
            onChange={(event) => draft.setPart({ ...part, quantity: Number(event.target.value) })}
          />
        </label>
      </div>
      <label>
        Location
        <select value={draft.locationMode === "new" ? "__new__" : part.locationId || ""} onChange={(event) => draft.selectLocation(event.target.value)}>
          <option value="">Unsorted</option>
          {locations.map((location) => (
            <option key={location.id} value={location.id}>
              {location.displayName}
            </option>
          ))}
          <option value="__new__">Create new location...</option>
        </select>
      </label>
      {draft.locationMode === "new" ? (
        <label>
          New location
          <input
            value={draft.customLocation}
            onChange={(event) => draft.updateCustomLocation(event.target.value)}
            placeholder="Drawer A3, resistor box, bench shelf"
          />
        </label>
      ) : null}
      <label>
        Aliases
        <textarea
          value={draft.aliasesText}
          rows={3}
          onChange={(event) => draft.setAliasesText(event.target.value)}
          placeholder="LM555, 555 timer, timer IC"
        />
      </label>
      <label>
        Notes
        <textarea
          value={part.notes}
          rows={3}
          onChange={(event) => draft.setPart({ ...part, notes: event.target.value })}
          placeholder="Voltage range, package, bin notes"
        />
      </label>
      <div className="inventory-form-actions">
        <button className="primary-button" disabled={saving || !part.displayName.trim()}>
          {saving ? "Saving..." : editingPart ? "Save changes" : "Add part"}
        </button>
        {editingPart && onCancel ? (
          <button className="ghost-button" type="button" disabled={saving} onClick={onCancel}>
            Cancel edit
          </button>
        ) : null}
      </div>
    </form>
  );
}
