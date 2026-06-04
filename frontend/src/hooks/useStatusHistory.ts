import { useEffect, useState } from "react";
import type { StatusPayload } from "../types";
import { pointFromStatus } from "../libs/performance/history";
import type { StatusHistoryPoint } from "../libs/performance/history";

export type { StatusHistoryPoint } from "../libs/performance/history";

export function useStatusHistory(status: StatusPayload | null, maxPoints = 180) {
  const [history, setHistory] = useState<StatusHistoryPoint[]>([]);

  useEffect(() => {
    if (!status) {
      return;
    }
    const next = pointFromStatus(status);
    setHistory((current) => {
      const previous = current[current.length - 1];
      if (previous && Math.abs(previous.sampledAt - next.sampledAt) < 250) {
        return current;
      }
      return [...current, next].slice(-maxPoints);
    });
  }, [maxPoints, status]);

  return history;
}
