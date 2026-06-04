import type { InventoryPartInput } from "../../types";

export const inventoryPartTypes = [
  "component",
  "ic",
  "resistor",
  "capacitor",
  "diode",
  "transistor",
  "sensor",
  "module",
  "board",
  "display",
  "tooling",
  "power"
];

export const emptyInventoryPartDraft: InventoryPartInput = {
  displayName: "",
  partType: "component",
  quantity: 1,
  location: "",
  notes: "",
  aliases: []
};

export type InventoryLocationMode = "existing" | "new";

export function parseAliases(value: string) {
  return value
    .split(/[,;\n]/)
    .map((alias) => alias.trim())
    .filter(Boolean);
}
