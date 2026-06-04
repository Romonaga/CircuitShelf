import { FormEvent, useEffect, useState } from "react";
import type { InventoryLocation, InventoryPart, InventoryPartInput } from "../../types";
import {
  emptyInventoryPartDraft,
  parseAliases,
  type InventoryLocationMode
} from "../../libs/inventory/partDraft";

export function useInventoryPartDraft({
  editingPart,
  locations,
  onSave
}: {
  editingPart?: InventoryPart | null;
  locations: InventoryLocation[];
  onSave: (part: InventoryPartInput) => Promise<boolean>;
}) {
  const [part, setPart] = useState<InventoryPartInput>(emptyInventoryPartDraft);
  const [aliasesText, setAliasesText] = useState("");
  const [customLocation, setCustomLocation] = useState("");
  const [locationMode, setLocationMode] = useState<InventoryLocationMode>("existing");

  useEffect(() => {
    if (!editingPart) {
      resetDraft();
      return;
    }
    const hasKnownLocation = Boolean(editingPart.locationId);
    setPart({
      id: editingPart.id,
      displayName: editingPart.displayName,
      partType: editingPart.partType,
      quantity: editingPart.quantity,
      locationId: editingPart.locationId,
      location: editingPart.location,
      notes: editingPart.notes,
      aliases: editingPart.aliases
    });
    setAliasesText(editingPart.aliases.join("\n"));
    setCustomLocation(hasKnownLocation ? "" : editingPart.location || "");
    setLocationMode(hasKnownLocation || !editingPart.location ? "existing" : "new");
  }, [editingPart]);

  function resetDraft() {
    setPart(emptyInventoryPartDraft);
    setAliasesText("");
    setCustomLocation("");
    setLocationMode("existing");
  }

  function selectLocation(value: string) {
    if (value === "__new__") {
      setLocationMode("new");
      setPart((current) => ({ ...current, locationId: null, location: "" }));
      setCustomLocation(part.location || "");
      return;
    }
    const location = locations.find((item) => item.id === value);
    setLocationMode("existing");
    setCustomLocation("");
    setPart((current) => ({ ...current, locationId: location?.id || null, location: location?.displayName || "" }));
  }

  function updateCustomLocation(value: string) {
    setCustomLocation(value);
    setPart((current) => ({ ...current, locationId: null, location: value }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const isNewLocation = locationMode === "new";
    const locationName = isNewLocation ? customLocation.trim() : part.location;
    const saved = await onSave({
      ...part,
      locationId: isNewLocation ? null : part.locationId,
      location: locationName,
      aliases: parseAliases(aliasesText)
    });
    if (saved && !editingPart) {
      resetDraft();
    }
  }

  return {
    aliasesText,
    customLocation,
    locationMode,
    part,
    selectLocation,
    setAliasesText,
    setPart,
    submit,
    updateCustomLocation
  };
}
