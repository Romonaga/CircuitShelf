import { useCallback, useEffect, useState } from "react";
import { deleteInventoryPart, getInventoryLocations, getInventoryParts, getProjectCandidates, saveInventoryPart } from "../libs/api";
import { errorMessage } from "../libs/errors";
import type { InventoryLocation, InventoryPart, InventoryPartInput, ProjectCandidate, ProjectCandidateFilter, ProjectMissingPartSummary } from "../types";

const emptyCandidates: ProjectCandidate[] = [];
const projectFinderPageSize = 32;

export function useInventory(isActive: boolean) {
  const [parts, setParts] = useState<InventoryPart[]>([]);
  const [locations, setLocations] = useState<InventoryLocation[]>([]);
  const [candidates, setCandidates] = useState<ProjectCandidate[]>(emptyCandidates);
  const [loading, setLoading] = useState(false);
  const [finding, setFinding] = useState(false);
  const [inventoryCount, setInventoryCount] = useState(0);
  const [candidateCount, setCandidateCount] = useState(0);
  const [filterCount, setFilterCount] = useState(0);
  const [candidateOffset, setCandidateOffset] = useState(0);
  const [candidateLimit, setCandidateLimit] = useState(projectFinderPageSize);
  const [candidateHasMore, setCandidateHasMore] = useState(false);
  const [candidateFilter, setCandidateFilter] = useState<ProjectCandidateFilter>("all");
  const [buildableCount, setBuildableCount] = useState(0);
  const [needsPartsCount, setNeedsPartsCount] = useState(0);
  const [missingPartSummary, setMissingPartSummary] = useState<ProjectMissingPartSummary[]>([]);
  const [error, setError] = useState("");

  const loadParts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await getInventoryParts();
      setParts(response.parts);
    } catch (err) {
      setError(errorMessage(err, "Could not load inventory"));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadLocations = useCallback(async () => {
    try {
      const response = await getInventoryLocations();
      setLocations(response.locations);
    } catch (err) {
      setError(errorMessage(err, "Could not load inventory locations"));
    }
  }, []);

  const refreshInventory = useCallback(async () => {
    await Promise.all([loadParts(), loadLocations()]);
  }, [loadLocations, loadParts]);

  const findProjects = useCallback(async (filter: ProjectCandidateFilter = "all", options: { append?: boolean } = {}) => {
    setFinding(true);
    setError("");
    const append = Boolean(options.append);
    const nextOffset = append ? candidateOffset + candidateLimit : 0;
    try {
      const response = await getProjectCandidates({
        limit: projectFinderPageSize,
        offset: nextOffset,
        filter
      });
      setInventoryCount(response.inventoryCount);
      setCandidateCount(response.candidateCount || 0);
      setFilterCount(response.filterCount ?? response.candidates.length);
      setCandidateOffset(response.offset || 0);
      setCandidateLimit(response.limit || projectFinderPageSize);
      setCandidateHasMore(Boolean(response.hasMore));
      setCandidateFilter(response.filter || filter);
      setBuildableCount(response.buildableCount || 0);
      setNeedsPartsCount(response.needsPartsCount || 0);
      setMissingPartSummary(response.missingPartSummary || []);
      setCandidates((current) => append ? [...current, ...response.candidates] : response.candidates);
    } catch (err) {
      setError(errorMessage(err, "Could not find project candidates"));
    } finally {
      setFinding(false);
    }
  }, [candidateLimit, candidateOffset]);

  const savePart = useCallback(
    async (part: InventoryPartInput) => {
      setError("");
      try {
        const response = await saveInventoryPart(part);
        setParts((current) => {
          const existing = current.filter((item) => item.id !== response.part.id);
          return [...existing, response.part].sort((left, right) => left.displayName.localeCompare(right.displayName));
        });
        await loadLocations();
        return response.part;
      } catch (err) {
        setError(errorMessage(err, "Could not save part"));
        return null;
      }
    },
    []
  );

  const removePart = useCallback(async (partId: string) => {
    setError("");
    try {
      await deleteInventoryPart(partId);
      setParts((current) => current.filter((part) => part.id !== partId));
      setCandidates(emptyCandidates);
      setCandidateCount(0);
      setFilterCount(0);
      setCandidateOffset(0);
      setCandidateHasMore(false);
      setCandidateFilter("all");
      setBuildableCount(0);
      setNeedsPartsCount(0);
      setMissingPartSummary([]);
      return true;
    } catch (err) {
      setError(errorMessage(err, "Could not remove part"));
      return false;
    }
  }, []);

  const updateQuantity = useCallback(
    async (partId: string, quantity: number) => {
      const part = parts.find((item) => item.id === partId);
      if (!part) {
        return null;
      }
      return savePart({
        id: part.id,
        displayName: part.displayName,
        partType: part.partType,
        quantity,
        locationId: part.locationId,
        location: part.location,
        notes: part.notes,
        aliases: part.aliases
      });
    },
    [parts, savePart]
  );

  useEffect(() => {
    if (isActive) {
      void refreshInventory();
    }
  }, [isActive, refreshInventory]);

  return {
    parts,
    locations,
    candidates,
    inventoryCount,
    candidateCount,
    filterCount,
    candidateOffset,
    candidateLimit,
    candidateHasMore,
    candidateFilter,
    buildableCount,
    needsPartsCount,
    missingPartSummary,
    loading,
    finding,
    error,
    loadParts,
    loadLocations,
    refreshInventory,
    findProjects,
    savePart,
    removePart,
    updateQuantity
  };
}
