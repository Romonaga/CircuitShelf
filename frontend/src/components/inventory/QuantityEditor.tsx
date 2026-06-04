import { useEffect, useState } from "react";
import type { InventoryPart } from "../../types";
import { formatNumber } from "../../libs/format";
import { LoadingSpinner } from "../LoadingSpinner";

export function QuantityEditor({
  part,
  saving,
  onChange
}: {
  part: InventoryPart;
  saving: boolean;
  onChange: (quantity: number) => void;
}) {
  const [draft, setDraft] = useState(String(part.quantity));

  useEffect(() => {
    setDraft(String(part.quantity));
  }, [part.quantity]);

  function commit(value: number) {
    const quantity = Math.max(0, Math.trunc(value || 0));
    setDraft(String(quantity));
    if (quantity !== part.quantity) {
      onChange(quantity);
    }
  }

  return (
    <div className="quantity-editor">
      <button type="button" aria-label={`Decrease ${part.displayName}`} disabled={saving || part.quantity <= 0} onClick={() => commit(part.quantity - 1)}>
        -
      </button>
      <input
        aria-label={`${part.displayName} quantity`}
        type="number"
        min="0"
        value={draft}
        disabled={saving}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => commit(Number(draft))}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.currentTarget.blur();
          }
        }}
      />
      <button type="button" aria-label={`Increase ${part.displayName}`} disabled={saving} onClick={() => commit(part.quantity + 1)}>
        +
      </button>
      {saving ? <LoadingSpinner className="quantity-spinner" /> : <span className="quantity-readout">{formatNumber(part.quantity)}</span>}
    </div>
  );
}
