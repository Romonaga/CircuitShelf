import { useCallback, useEffect, useState } from "react";
import { deleteInventoryPart, getInventoryParts, getProjectCandidates, saveInventoryPart } from "../api";
import { errorMessage } from "../lib/errors";
import type { InventoryPart, InventoryPartInput, ProjectCandidate } from "../types";

const emptyCandidates: ProjectCandidate[] = [];

export function useInventory(isActive: boolean) {
  const [parts, setParts] = useState<InventoryPart[]>([]);
  const [candidates, setCandidates] = useState<ProjectCandidate[]>(emptyCandidates);
  const [loading, setLoading] = useState(false);
  const [finding, setFinding] = useState(false);
  const [inventoryCount, setInventoryCount] = useState(0);
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

  const findProjects = useCallback(async () => {
    setFinding(true);
    setError("");
    try {
      const response = await getProjectCandidates(32);
      setInventoryCount(response.inventoryCount);
      setCandidates(response.candidates);
    } catch (err) {
      setError(errorMessage(err, "Could not find project candidates"));
    } finally {
      setFinding(false);
    }
  }, []);

  const savePart = useCallback(
    async (part: InventoryPartInput) => {
      setError("");
      try {
        const response = await saveInventoryPart(part);
        setParts((current) => {
          const existing = current.filter((item) => item.id !== response.part.id);
          return [...existing, response.part].sort((left, right) => left.displayName.localeCompare(right.displayName));
        });
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
      return true;
    } catch (err) {
      setError(errorMessage(err, "Could not remove part"));
      return false;
    }
  }, []);

  useEffect(() => {
    if (isActive) {
      void loadParts();
    }
  }, [isActive, loadParts]);

  return {
    parts,
    candidates,
    inventoryCount,
    loading,
    finding,
    error,
    loadParts,
    findProjects,
    savePart,
    removePart
  };
}
