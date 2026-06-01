import { FormEvent, useEffect, useState } from "react";
import type { InventoryPart, InventoryPartInput } from "../types";

const partTypes = ["component", "ic", "resistor", "capacitor", "diode", "transistor", "sensor", "module", "board", "display", "tooling", "power"];

const initialPart: InventoryPartInput = {
  displayName: "",
  partType: "component",
  quantity: 1,
  location: "",
  notes: "",
  aliases: []
};

export function InventoryPartForm({
  saving,
  editingPart,
  onCancel,
  onSave
}: {
  saving: boolean;
  editingPart?: InventoryPart | null;
  onCancel?: () => void;
  onSave: (part: InventoryPartInput) => Promise<boolean>;
}) {
  const [part, setPart] = useState<InventoryPartInput>(initialPart);
  const [aliasesText, setAliasesText] = useState("");

  useEffect(() => {
    if (!editingPart) {
      setPart(initialPart);
      setAliasesText("");
      return;
    }
    setPart({
      id: editingPart.id,
      displayName: editingPart.displayName,
      partType: editingPart.partType,
      quantity: editingPart.quantity,
      location: editingPart.location,
      notes: editingPart.notes,
      aliases: editingPart.aliases
    });
    setAliasesText(editingPart.aliases.join("\n"));
  }, [editingPart]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const saved = await onSave({
      ...part,
      aliases: aliasesText
        .split(/[,;\n]/)
        .map((alias) => alias.trim())
        .filter(Boolean)
    });
    if (saved && !editingPart) {
      setPart(initialPart);
      setAliasesText("");
    }
  }

  return (
    <form className="inventory-part-form" onSubmit={submit}>
      <label>
        Part
        <input
          value={part.displayName}
          onChange={(event) => setPart({ ...part, displayName: event.target.value })}
          placeholder="NE555, 10 kOhm resistor, Arduino Uno"
        />
      </label>
      <div className="inventory-form-grid">
        <label>
          Type
          <select value={part.partType} onChange={(event) => setPart({ ...part, partType: event.target.value })}>
            {partTypes.map((item) => (
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
            onChange={(event) => setPart({ ...part, quantity: Number(event.target.value) })}
          />
        </label>
      </div>
      <label>
        Location
        <input
          value={part.location}
          onChange={(event) => setPart({ ...part, location: event.target.value })}
          placeholder="Drawer A3, resistor box, bench shelf"
        />
      </label>
      <label>
        Aliases
        <textarea
          value={aliasesText}
          rows={3}
          onChange={(event) => setAliasesText(event.target.value)}
          placeholder="LM555, 555 timer, timer IC"
        />
      </label>
      <label>
        Notes
        <textarea
          value={part.notes}
          rows={3}
          onChange={(event) => setPart({ ...part, notes: event.target.value })}
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
