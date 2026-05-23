import { useState } from "react";
import { applyInventoryImport, previewInventoryImport } from "../api";
import { errorMessage } from "../lib/errors";
import type { InventoryImportItem } from "../types";
import { ErrorMessage } from "./ErrorMessage";

export function InventoryImportPanel({ onImported }: { onImported: (count: number) => void }) {
  const [text, setText] = useState("");
  const [items, setItems] = useState<InventoryImportItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function preview() {
    setBusy(true);
    setError("");
    try {
      const response = await previewInventoryImport(text);
      setItems(response.items.map((item) => ({ ...item, selected: true })));
    } catch (err) {
      setError(errorMessage(err, "Could not parse inventory list"));
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    const selected = items.filter((item) => item.selected);
    if (!selected.length) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await applyInventoryImport(selected);
      setText("");
      setItems([]);
      onImported(response.count);
    } catch (err) {
      setError(errorMessage(err, "Could not import inventory"));
    } finally {
      setBusy(false);
    }
  }

  function updateItem(index: number, patch: Partial<InventoryImportItem>) {
    setItems((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  }

  return (
    <section className="inventory-import-panel">
      <h3>Bulk import</h3>
      <textarea
        value={text}
        rows={6}
        onChange={(event) => setText(event.target.value)}
        placeholder={"20x NE555\nbunch of 10k resistors\n15 raspberry pi 4/5\nlogic chips 74HC, 4000 series"}
      />
      <div className="query-actions">
        <button className="ghost-button" type="button" disabled={busy || !text.trim()} onClick={() => void preview()}>
          {busy ? "Parsing..." : "Preview import"}
        </button>
        <button className="primary-button" type="button" disabled={busy || !items.some((item) => item.selected)} onClick={() => void apply()}>
          Import selected
        </button>
      </div>
      <ErrorMessage message={error} />
      {items.length ? (
        <div className="inventory-import-list">
          {items.map((item, index) => (
            <article key={`${item.rawLine}-${index}`} className="inventory-import-row">
              <label className="check-row">
                <input type="checkbox" checked={Boolean(item.selected)} onChange={(event) => updateItem(index, { selected: event.target.checked })} />
                {item.action === "merge" ? "Merge" : "Create"}
              </label>
              <div className="inventory-import-fields">
                <input value={item.displayName} onChange={(event) => updateItem(index, { displayName: event.target.value })} />
                <select value={item.partType} onChange={(event) => updateItem(index, { partType: event.target.value })}>
                  {["component", "ic", "resistor", "capacitor", "diode", "transistor", "sensor", "module", "board", "display", "tooling", "power"].map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
                <input type="number" min="0" value={item.quantity} onChange={(event) => updateItem(index, { quantity: Number(event.target.value) })} />
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
      ) : null}
    </section>
  );
}
