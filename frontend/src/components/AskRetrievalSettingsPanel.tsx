import { FormEvent, useEffect, useState } from "react";
import { getUserPreference, updateUserPreference } from "../libs/api";
import type { AppConfig, QueryOptions } from "../types";
import {
  ASK_RETRIEVAL_PREFERENCE_KEY,
  preferenceFromResolved,
  resolveAskPreferences,
  type AskRetrievalPreference,
} from "../libs/askPreferences";
import { errorMessage } from "../libs/errors";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";

export function AskRetrievalSettingsPanel({ config }: { config: AppConfig }) {
  const [model, setModel] = useState(config.defaultModel);
  const [options, setOptions] = useState<QueryOptions>(config.defaults);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const response = await getUserPreference<AskRetrievalPreference>(ASK_RETRIEVAL_PREFERENCE_KEY);
        if (cancelled) {
          return;
        }
        const resolved = resolveAskPreferences(config, response.value);
        setModel(resolved.model);
        setOptions(resolved.options);
      } catch (err) {
        setError(errorMessage(err, "Could not load Ask defaults"));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [config]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");
    try {
      await updateUserPreference(ASK_RETRIEVAL_PREFERENCE_KEY, preferenceFromResolved(model, options));
      setMessage("Ask defaults saved.");
    } catch (err) {
      setError(errorMessage(err, "Could not save Ask defaults"));
    } finally {
      setSaving(false);
    }
  }

  function resetDefaults() {
    const resolved = resolveAskPreferences(config, null);
    setModel(resolved.model);
    setOptions(resolved.options);
    setMessage("");
  }

  return (
    <form className="account-card ask-settings-card" onSubmit={save}>
      <SectionHeader
        title="Ask retrieval defaults"
        description={loading ? "Loading your retrieval settings..." : "Personal defaults used by the Ask page for model selection, context size, retrieval, and cache behavior."}
        actions={
          <button className="ghost-button" type="button" onClick={resetDefaults} disabled={saving}>
            Reset
          </button>
        }
      />
      <div className="ask-settings-grid">
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
          Distance threshold
          <input
            type="number"
            step="0.1"
            min="0.1"
            value={options.distanceThreshold}
            onChange={(event) => setOptions({ ...options, distanceThreshold: Number(event.target.value) })}
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
        <label className="check-row">
          <input
            type="checkbox"
            checked={options.showFullText}
            onChange={(event) => setOptions({ ...options, showFullText: event.target.checked })}
          />
          Show full source text
        </label>
        <label className="check-row">
          <input
            type="checkbox"
            checked={options.bypassCache}
            onChange={(event) => setOptions({ ...options, bypassCache: event.target.checked })}
          />
          Bypass response cache
        </label>
      </div>
      <ErrorMessage message={error} />
      {message ? <div className="success-message">{message}</div> : null}
      <button className="primary-button" disabled={saving || loading}>
        {saving ? "Saving..." : "Save Ask defaults"}
      </button>
    </form>
  );
}
