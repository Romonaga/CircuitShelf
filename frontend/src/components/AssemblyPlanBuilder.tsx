import { FormEvent, useState } from "react";
import { buildAssemblyPlan } from "../api";
import { errorMessage } from "../lib/errors";
import type { AppConfig, AssemblyPlan, QueryOptions } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { LoadingSpinner } from "./LoadingSpinner";
import { SectionHeader } from "./SectionHeader";

export function AssemblyPlanBuilder({
  config,
  onPlanCreated
}: {
  config: AppConfig;
  onPlanCreated: (plan: AssemblyPlan) => void;
}) {
  const [objective, setObjective] = useState("");
  const [model, setModel] = useState(config.defaultModel);
  const [options, setOptions] = useState<QueryOptions>({ ...config.defaults, bypassCache: true, showFullText: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const canSubmit = objective.trim().length > 0 && !busy;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await buildAssemblyPlan({
        objective,
        model,
        topK: options.topK,
        distanceThreshold: options.distanceThreshold,
        maxTokens: options.maxTokens,
        strategy: options.strategy
      });
      if (!response.plan) {
        throw new Error(response.error || "No assembly plan was created.");
      }
      setObjective("");
      onPlanCreated(response.plan);
    } catch (err) {
      setError(errorMessage(err, "Could not create assembly plan"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="assembly-builder" onSubmit={submit}>
      <SectionHeader
        title="Circuit assembly"
        description="Create a source-grounded build plan with wiring steps, checks, warnings, and bench follow-up."
      />
      <textarea
        value={objective}
        onChange={(event) => setObjective(event.target.value)}
        placeholder="Example: Build a 555 astable LED blinker on a breadboard with pin-by-pin wiring."
        rows={5}
      />
      <div className="assembly-builder-controls">
        <label>
          Model
          <select value={model} onChange={(event) => setModel(event.target.value)}>
            {config.models.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          Strategy
          <select value={options.strategy} onChange={(event) => setOptions({ ...options, strategy: event.target.value })}>
            {config.retrievalStrategies.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          Top K
          <input
            type="number"
            min="1"
            max="80"
            value={options.topK}
            onChange={(event) => setOptions({ ...options, topK: Number(event.target.value) })}
          />
        </label>
        <label>
          Context tokens
          <input
            type="number"
            min="100"
            step="100"
            value={options.maxTokens}
            onChange={(event) => setOptions({ ...options, maxTokens: Number(event.target.value) })}
          />
        </label>
      </div>
      <button className="primary-button assembly-build-button" disabled={!canSubmit}>
        {busy ? (
          <>
            <LoadingSpinner className="button-spinner" />
            Building plan
          </>
        ) : (
          "Build assembly plan"
        )}
      </button>
      <ErrorMessage message={error} />
    </form>
  );
}
