export interface InventoryPart {
  id: string;
  userId?: number;
  displayName: string;
  normalizedName?: string;
  partType: string;
  quantity: number;
  locationId?: string | null;
  location: string;
  notes: string;
  aliases: string[];
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface InventoryLocation {
  id: string;
  userId?: number;
  displayName: string;
  normalizedName?: string;
  notes?: string;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface InventoryPartInput {
  id?: string;
  displayName: string;
  partType: string;
  quantity: number;
  locationId?: string | null;
  location: string;
  notes: string;
  aliases: string[];
}

export interface InventoryImportItem extends InventoryPartInput {
  rawLine: string;
  normalizedName?: string;
  confidence: number;
  warnings: string[];
  action?: "create" | "merge" | string;
  existingPartId?: string | null;
  selected?: boolean;
}

export interface InventoryImportPreview {
  items: InventoryImportItem[];
  count: number;
  source?: string;
  model?: string | null;
  paidBy?: string | null;
  estimatedCost?: number | null;
}

export interface ProjectCandidatePart {
  id?: string;
  displayName?: string;
  name?: string;
  partType?: string;
  type?: string;
  quantity?: number;
  location?: string;
}

export interface ProjectCandidate {
  id: string;
  kind: "project_chunk" | "component_reference" | string;
  title: string;
  objective: string;
  summary: string;
  source: string;
  displayName: string;
  page?: number | null;
  chunkIndex?: number | null;
  matchedParts: ProjectCandidatePart[];
  matchedPartCount: number;
  requiredParts: ProjectCandidatePart[];
  missingParts: ProjectCandidatePart[];
  suggestedSubstitutions: Array<Record<string, string>>;
  buildable: boolean;
  score: number;
}

export interface ProjectMissingPartSummary {
  name: string;
  type: string;
  count: number;
  exampleTitles: string[];
}

export interface ProjectFinderResponse {
  inventoryCount: number;
  termCount?: number;
  buildableCount?: number;
  needsPartsCount?: number;
  missingPartSummary?: ProjectMissingPartSummary[];
  candidates: ProjectCandidate[];
}
