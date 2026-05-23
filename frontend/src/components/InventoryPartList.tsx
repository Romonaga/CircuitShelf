import { useMemo, useState } from "react";
import type { InventoryPart } from "../types";
import { formatNumber } from "../lib/format";

type SortKey = "displayName" | "partType" | "quantity" | "location";
type SortDirection = "asc" | "desc";

const sortLabels: Record<SortKey, string> = {
  displayName: "Part",
  partType: "Type",
  quantity: "Qty",
  location: "Location"
};

export function InventoryPartList({
  parts,
  loading,
  onRemove
}: {
  parts: InventoryPart[];
  loading: boolean;
  onRemove: (partId: string) => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("partType");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const sortedParts = useMemo(() => {
    return [...parts].sort((left, right) => {
      const direction = sortDirection === "asc" ? 1 : -1;
      if (sortKey === "quantity") {
        return (left.quantity - right.quantity) * direction || left.displayName.localeCompare(right.displayName);
      }
      return String(left[sortKey] || "").localeCompare(String(right[sortKey] || "")) * direction || left.displayName.localeCompare(right.displayName);
    });
  }, [parts, sortDirection, sortKey]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection("asc");
  }

  if (loading && !parts.length) {
    return <div className="empty-state compact">Loading inventory...</div>;
  }

  if (!parts.length) {
    return <div className="empty-state compact">No lab parts stored yet.</div>;
  }

  return (
    <div className="inventory-part-list inventory-table-wrap">
      <table className="inventory-table">
        <thead>
          <tr>
            {(["displayName", "partType", "quantity", "location"] as SortKey[]).map((key) => (
              <th key={key} scope="col">
                <button type="button" onClick={() => toggleSort(key)}>
                  {sortLabels[key]}
                  {sortKey === key ? <span>{sortDirection === "asc" ? "▲" : "▼"}</span> : null}
                </button>
              </th>
            ))}
            <th scope="col">Aliases</th>
            <th scope="col">Notes</th>
            <th scope="col" className="inventory-table-action">Action</th>
          </tr>
        </thead>
        <tbody>
          {sortedParts.map((part) => (
            <tr key={part.id}>
              <td className="inventory-part-name" title={part.displayName}>
                {part.displayName}
              </td>
              <td>{part.partType}</td>
              <td className="inventory-table-number">{formatNumber(part.quantity)}</td>
              <td title={part.location}>{part.location || "Unsorted"}</td>
              <td title={part.aliases.join(", ")}>{part.aliases.length ? part.aliases.join(", ") : "None"}</td>
              <td title={part.notes}>{part.notes || "None"}</td>
              <td className="inventory-table-action">
                <button className="ghost-button danger-button compact-button" type="button" onClick={() => onRemove(part.id)}>
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
