import { useEffect, useState } from "react";
import { getAssemblyLearning, updateAssemblyLearning } from "../api";
import { errorMessage } from "../lib/errors";
import type { AssemblyLearningSession, AssemblyPlan } from "../types";
import { ErrorMessage } from "./ErrorMessage";

export function AssemblyLearningPanel({ plan }: { plan: AssemblyPlan }) {
  const [learning, setLearning] = useState<AssemblyLearningSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setError("");
      try {
        const response = await getAssemblyLearning(plan.id);
        if (!cancelled) {
          setLearning(response.learning);
        }
      } catch (err) {
        if (!cancelled) {
          setError(errorMessage(err, "Could not load learning mode"));
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [plan.id]);

  async function move(action: string) {
    setBusy(true);
    setError("");
    try {
      const response = await updateAssemblyLearning(plan.id, action);
      setLearning(response.learning);
    } catch (err) {
      setError(errorMessage(err, "Could not update learning mode"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="assembly-tool-panel">
      <h3>Learning mode</h3>
      <ErrorMessage message={error} />
      {learning?.currentStep ? (
        <div className="assembly-learning-card">
          <small>
            Step {learning.currentOrdinal} of {learning.stepCount}
          </small>
          <strong>{learning.currentStep.title}</strong>
          <p>{learning.prompt}</p>
          <div className="assembly-export-controls">
            <button className="ghost-button compact-button" type="button" disabled={busy || learning.currentOrdinal <= 1} onClick={() => void move("previous")}>
              Previous
            </button>
            <button className="primary-button compact-button" type="button" disabled={busy || learning.currentOrdinal >= learning.stepCount} onClick={() => void move("next")}>
              Next lesson step
            </button>
          </div>
        </div>
      ) : (
        <div className="empty-state compact">No steps available for learning mode.</div>
      )}
    </section>
  );
}
