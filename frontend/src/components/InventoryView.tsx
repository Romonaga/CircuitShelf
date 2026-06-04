import { useMemo, useState } from "react";
import type { InventoryPart, InventoryPartInput } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { InventoryPartForm } from "./InventoryPartForm";
import { InventoryImportPanel } from "./InventoryImportPanel";
import { InventoryPartList } from "./InventoryPartList";
import { SectionHeader } from "./SectionHeader";
import { useInventory } from "../hooks/useInventory";
import { formatNumber } from "../libs/format";

export function InventoryView({ isActive }: { isActive: boolean }) {
  const {
    parts,
    locations,
    loading,
    error,
    savePart,
    removePart,
    updateQuantity,
    refreshInventory
  } = useInventory(isActive);
  const [saving, setSaving] = useState(false);
  const [quantitySavingId, setQuantitySavingId] = useState("");
  const [editingPart, setEditingPart] = useState<InventoryPart | null>(null);
  const [message, setMessage] = useState("");

  const inventoryStats = useMemo(() => {
    const locations = new Set(parts.map((part) => part.location).filter(Boolean));
    const types = new Set(parts.map((part) => part.partType).filter(Boolean));
    return {
      count: parts.length,
      quantity: parts.reduce((total, part) => total + part.quantity, 0),
      locations: locations.size,
      types: types.size
    };
  }, [parts]);

  async function submitPart(part: InventoryPartInput) {
    setSaving(true);
    setMessage("");
    try {
      const saved = await savePart(part);
      if (saved) {
        setMessage(`${saved.displayName} ${part.id ? "updated" : "added to inventory"}.`);
        setEditingPart(null);
        return true;
      }
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function saveQuantity(partId: string, quantity: number) {
    setQuantitySavingId(partId);
    setMessage("");
    try {
      const saved = await updateQuantity(partId, quantity);
      if (saved) {
        setMessage(`${saved.displayName} quantity set to ${formatNumber(saved.quantity)}.`);
      }
    } finally {
      setQuantitySavingId("");
    }
  }

  async function removeInventoryPart(partId: string) {
    setMessage("");
    const removed = await removePart(partId);
    if (removed) {
      setEditingPart((current) => (current?.id === partId ? null : current));
      setMessage("Inventory part removed.");
    }
  }

  return (
    <section className="inventory-workflow">
      <header className="inventory-command-panel">
        <div>
          <SectionHeader title="Lab inventory" description="Track bins, quantities, aliases, and notes without leaving the bench workflow." />
        </div>
        <div className="inventory-stat-strip">
          <InventoryMetric label="Parts" value={inventoryStats.count} />
          <InventoryMetric label="Total qty" value={inventoryStats.quantity} />
          <InventoryMetric label="Types" value={inventoryStats.types} />
          <InventoryMetric label="Locations" value={inventoryStats.locations} />
        </div>
      </header>

      <div className="inventory-layout">
        <aside className="inventory-entry-column">
          <section className="inventory-panel">
            <SectionHeader
              title={editingPart ? "Edit part" : "Add part"}
              description={editingPart ? "Update quantity, aliases, location, notes, or display name." : "Single component, board, tool, or module."}
            />
            <InventoryPartForm
              saving={saving}
              editingPart={editingPart}
              locations={locations}
              onCancel={() => setEditingPart(null)}
              onSave={submitPart}
            />
          </section>
          <InventoryImportPanel
            locations={locations}
            onImported={(count) => {
              setMessage(`${count} inventory items imported.`);
              void refreshInventory();
            }}
          />
        </aside>

        <section className="inventory-stock-panel">
          <div className="inventory-results-heading">
            <SectionHeader title="Stockroom" description={loading ? "Refreshing inventory..." : `${formatNumber(parts.length)} stored parts`} />
          </div>
          <ErrorMessage message={error} />
          {message ? <div className="success-message">{message}</div> : null}
          <InventoryPartList
            parts={parts}
            loading={loading}
            savingQuantityId={quantitySavingId}
            selectedPartId={editingPart?.id}
            onSelect={setEditingPart}
            onQuantityChange={(partId, quantity) => void saveQuantity(partId, quantity)}
            onRemove={(partId) => void removeInventoryPart(partId)}
          />
        </section>
      </div>
    </section>
  );
}

function InventoryMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="inventory-metric">
      <span>{label}</span>
      <strong>{formatNumber(value)}</strong>
    </div>
  );
}
