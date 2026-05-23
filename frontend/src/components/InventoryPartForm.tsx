import { FormEvent, useState } from "react";
import type { InventoryPartInput } from "../types";

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
  onSave
}: {
  saving: boolean;
  onSave: (part: InventoryPartInput) => Promise<boolean>;
}) {
  const [part, setPart] = useState<InventoryPartInput>(initialPart);
  const [aliasesText, setAliasesText] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const saved = await onSave({
      ...part,
      aliases: aliasesText
        .split(/[,;\n]/)
        .map((alias) => alias.trim())
        .filter(Boolean)
    });
    if (saved) {
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
      <button className="primary-button" disabled={saving || !part.displayName.trim()}>
        {saving ? "Saving..." : "Add part"}
      </button>
    </form>
  );
}
