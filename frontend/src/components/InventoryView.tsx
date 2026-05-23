import { useMemo, useState } from "react";
import type { InventoryPartInput } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { InventoryPartForm } from "./InventoryPartForm";
import { InventoryImportPanel } from "./InventoryImportPanel";
import { InventoryPartList } from "./InventoryPartList";
import { SectionHeader } from "./SectionHeader";
import { useInventory } from "../hooks/useInventory";
import { formatNumber } from "../lib/format";

export function InventoryView({ isActive }: { isActive: boolean }) {
  const {
    parts,
    loading,
    error,
    savePart,
    removePart,
    loadParts
  } = useInventory(isActive);
  const [saving, setSaving] = useState(false);
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
        setMessage(`${saved.displayName} added to inventory.`);
        return true;
      }
      return false;
    } finally {
      setSaving(false);
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
            <SectionHeader title="Add part" description="Single component, board, tool, or module." />
            <InventoryPartForm saving={saving} onSave={submitPart} />
          </section>
          <InventoryImportPanel
            onImported={(count) => {
              setMessage(`${count} inventory items imported.`);
              void loadParts();
            }}
          />
        </aside>

        <section className="inventory-stock-panel">
          <div className="inventory-results-heading">
            <SectionHeader title="Stockroom" description={loading ? "Refreshing inventory..." : `${formatNumber(parts.length)} stored parts`} />
          </div>
          <ErrorMessage message={error} />
          {message ? <div className="success-message">{message}</div> : null}
          <InventoryPartList parts={parts} loading={loading} onRemove={(partId) => void removePart(partId)} />
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
