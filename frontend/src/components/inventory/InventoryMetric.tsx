import { formatNumber } from "../../libs/format";

export function InventoryMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="inventory-metric">
      <span>{label}</span>
      <strong>{formatNumber(value)}</strong>
    </div>
  );
}
