import type { InventoryImportItem, InventoryImportPreview, InventoryLocation, InventoryPart, InventoryPartInput, ProjectFinderResponse } from "../../types";
import { requestJson } from "./core";

export function getInventoryParts(): Promise<{ parts: InventoryPart[] }> {
  return requestJson<{ parts: InventoryPart[] }>("/api/inventory/parts");
}

export function getInventoryLocations(): Promise<{ locations: InventoryLocation[] }> {
  return requestJson<{ locations: InventoryLocation[] }>("/api/inventory/locations");
}

export function saveInventoryLocation(location: Pick<InventoryLocation, "displayName"> & Partial<InventoryLocation>): Promise<{ location: InventoryLocation }> {
  return requestJson<{ location: InventoryLocation }>("/api/inventory/locations", {
    method: "POST",
    body: JSON.stringify(location)
  });
}

export function saveInventoryPart(part: InventoryPartInput): Promise<{ part: InventoryPart }> {
  return requestJson<{ part: InventoryPart }>("/api/inventory/parts", {
    method: "POST",
    body: JSON.stringify(part)
  });
}

export function deleteInventoryPart(partId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/inventory/parts/${encodeURIComponent(partId)}`, {
    method: "DELETE"
  });
}

export function previewInventoryImport(text: string): Promise<InventoryImportPreview> {
  return requestJson<InventoryImportPreview>("/api/inventory/import/preview", {
    method: "POST",
    body: JSON.stringify({ text })
  });
}

export function applyInventoryImport(items: InventoryImportItem[]): Promise<{ parts: InventoryPart[]; count: number }> {
  return requestJson<{ parts: InventoryPart[]; count: number }>("/api/inventory/import/apply", {
    method: "POST",
    body: JSON.stringify({ items })
  });
}

export function previewInventoryPhotoImport(file: File, note = ""): Promise<InventoryImportPreview> {
  const body = new FormData();
  body.append("file", file);
  body.append("note", note);
  return requestJson<InventoryImportPreview>("/api/inventory/import/photo-preview", {
    method: "POST",
    body
  });
}

export function getProjectCandidates(limit = 24): Promise<ProjectFinderResponse> {
  return requestJson<ProjectFinderResponse>(`/api/inventory/project-candidates?limit=${encodeURIComponent(String(limit))}`);
}
