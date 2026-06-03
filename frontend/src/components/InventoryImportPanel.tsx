import { useState } from "react";
import { applyInventoryImport, previewInventoryImport, previewInventoryPhotoImport } from "../api";
import { errorMessage } from "../lib/errors";
import type { InventoryImportItem, InventoryLocation } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { InventoryImportRows } from "./InventoryImportRows";

export function InventoryImportPanel({ locations, onImported }: { locations: InventoryLocation[]; onImported: (count: number) => void }) {
  const [text, setText] = useState("");
  const [items, setItems] = useState<InventoryImportItem[]>([]);
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoNote, setPhotoNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sourceNote, setSourceNote] = useState("");

  async function preview() {
    setBusy(true);
    setError("");
    try {
      const response = await previewInventoryImport(text);
      setItems(response.items.map((item) => ({ ...item, selected: true })));
      setSourceNote(`${response.count} text rows ready. Checked rows will be imported; merge rows add to existing stock.`);
    } catch (err) {
      setError(errorMessage(err, "Could not parse inventory list"));
    } finally {
      setBusy(false);
    }
  }

  async function previewPhoto() {
    if (!photo) {
      return;
    }
    setBusy(true);
    setError("");
    setSourceNote("");
    try {
      const response = await previewInventoryPhotoImport(photo, photoNote);
      setItems(response.items.map((item) => ({ ...item, selected: true })));
      const cost = response.estimatedCost != null ? ` Estimated cost $${response.estimatedCost.toFixed(6)}.` : "";
      setSourceNote(`${response.count} photo suggestions ready from ${response.model || "OpenAI"}.${cost}`);
    } catch (err) {
      setError(errorMessage(err, "Could not analyze inventory photo"));
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
      setPhoto(null);
      setPhotoNote("");
      setSourceNote("");
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
      <p className="muted-copy">Preview turns notes or a photo into editable rows. Import selected writes only the checked rows.</p>
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
      <div className="inventory-photo-import">
        <h4>Photo import</h4>
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          onChange={(event) => setPhoto(event.target.files?.[0] || null)}
        />
        <input
          value={photoNote}
          onChange={(event) => setPhotoNote(event.target.value)}
          placeholder="Optional note, e.g. drawer label or expected part family"
        />
        <button className="ghost-button" type="button" disabled={busy || !photo} onClick={() => void previewPhoto()}>
          {busy ? "Analyzing..." : "Preview photo"}
        </button>
      </div>
      <ErrorMessage message={error} />
      {sourceNote ? <div className="info-message compact">{sourceNote}</div> : null}
      <InventoryImportRows items={items} locations={locations} onUpdate={updateItem} />
    </section>
  );
}
