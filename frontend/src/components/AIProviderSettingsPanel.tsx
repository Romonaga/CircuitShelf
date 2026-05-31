import { FormEvent, useEffect, useMemo, useState } from "react";
import type { AIModelPricing, AIProviderSettings, AIProviderSettingsPayload } from "../types";
import { errorMessage } from "../lib/errors";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";

const defaultSettings: AIProviderSettings = {
  scope: "user",
  provider: "openai",
  enabled: false,
  hasApiKey: false,
  keyPreview: "",
  keyPolicy: "user_when_available",
  assistMode: "auto",
  defaultModel: "",
  monthlyBudget: 0,
  warnPercent: 80,
  stopPercent: 100
};

export function AIProviderSettingsPanel({
  title,
  description,
  loadSettings,
  saveSettings,
  canManage,
  showKeyPolicy = true,
  showBudget = true
}: {
  title: string;
  description: string;
  loadSettings: () => Promise<{ settings: AIProviderSettings; pricing: AIModelPricing[] }>;
  saveSettings: (payload: AIProviderSettingsPayload) => Promise<{ settings: AIProviderSettings }>;
  canManage: boolean;
  showKeyPolicy?: boolean;
  showBudget?: boolean;
}) {
  const [settings, setSettings] = useState<AIProviderSettings>(defaultSettings);
  const [pricing, setPricing] = useState<AIModelPricing[]>([]);
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setBusy(true);
    setError("");
    loadSettings()
      .then((response) => {
        if (!active) {
          return;
        }
        const loaded = response.settings;
        const firstActiveModel = response.pricing.find((item) => item.isActive)?.modelName || "";
        setPricing(response.pricing);
        setSettings({
          ...defaultSettings,
          ...loaded,
          defaultModel: loaded.defaultModel || firstActiveModel
        });
      })
      .catch((err) => {
        if (active) {
          setError(errorMessage(err, "Could not load AI provider settings"));
        }
      })
      .finally(() => {
        if (active) {
          setBusy(false);
        }
      });
    return () => {
      active = false;
    };
  }, [loadSettings]);

  const selectedPrice = useMemo(
    () => pricing.find((item) => item.modelName === settings.defaultModel),
    [pricing, settings.defaultModel]
  );

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canManage) {
      return;
    }
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await saveSettings({
        enabled: settings.enabled,
        apiKey: apiKey.trim() || undefined,
        clearApiKey,
        keyPolicy: settings.keyPolicy,
        assistMode: settings.assistMode,
        defaultModel: settings.defaultModel,
        monthlyBudget: settings.monthlyBudget,
        warnPercent: settings.warnPercent,
        stopPercent: settings.stopPercent
      });
      setSettings(response.settings);
      setApiKey("");
      setClearApiKey(false);
      setMessage("AI provider settings saved.");
    } catch (err) {
      setError(errorMessage(err, "Could not save AI provider settings"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="ai-provider-panel" onSubmit={submit}>
      <SectionHeader title={title} description={busy ? "Loading..." : description} />
      <ErrorMessage message={error} />

      <div className="ai-provider-grid">
        <label className="inline-check ai-provider-enabled">
          <input
            type="checkbox"
            checked={settings.enabled}
            disabled={!canManage}
            onChange={(event) => setSettings({ ...settings, enabled: event.target.checked })}
          />
          Enable OpenAI assist
        </label>
        <label>
          Assist mode
          <select
            value={settings.assistMode}
            disabled={!canManage}
            onChange={(event) => setSettings({ ...settings, assistMode: event.target.value })}
          >
            <option value="auto">Auto</option>
            <option value="always">Always</option>
            <option value="off">Off</option>
          </select>
        </label>
        {showKeyPolicy ? (
          <label>
            Key policy
            <select
              value={settings.keyPolicy}
              disabled={!canManage}
              onChange={(event) => setSettings({ ...settings, keyPolicy: event.target.value })}
            >
              <option value="entity">Entity key</option>
              <option value="user_when_available">User key when available</option>
              <option value="user_only">User key only</option>
              <option value="system">System key</option>
            </select>
          </label>
        ) : null}
        <label>
          Default model
          <select
            value={settings.defaultModel}
            disabled={!canManage}
            onChange={(event) => setSettings({ ...settings, defaultModel: event.target.value })}
          >
            <option value="">Select a model</option>
            {pricing.map((item) => (
              <option key={item.modelName} value={item.modelName}>
                {item.modelName}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="ai-key-row">
        <div>
          <strong>{settings.hasApiKey ? "Key stored" : "No key stored"}</strong>
          <span>{settings.keyPreview || "Paste a key to store it encrypted."}</span>
        </div>
        <label>
          Replace key
          <input
            type="password"
            value={apiKey}
            disabled={!canManage || clearApiKey}
            onChange={(event) => setApiKey(event.target.value)}
            autoComplete="off"
            placeholder="sk-..."
          />
        </label>
        <label className="inline-check">
          <input
            type="checkbox"
            checked={clearApiKey}
            disabled={!canManage}
            onChange={(event) => setClearApiKey(event.target.checked)}
          />
          Clear stored key
        </label>
      </div>

      {showBudget ? (
        <div className="ai-provider-grid compact">
          <label>
            Monthly budget
            <input
              type="number"
              min={0}
              step="0.01"
              value={settings.monthlyBudget}
              disabled={!canManage}
              onChange={(event) => setSettings({ ...settings, monthlyBudget: Number(event.target.value) })}
            />
          </label>
          <label>
            Warn %
            <input
              type="number"
              min={1}
              max={100}
              value={settings.warnPercent}
              disabled={!canManage}
              onChange={(event) => setSettings({ ...settings, warnPercent: Number(event.target.value) })}
            />
          </label>
          <label>
            Stop %
            <input
              type="number"
              min={1}
              max={100}
              value={settings.stopPercent}
              disabled={!canManage}
              onChange={(event) => setSettings({ ...settings, stopPercent: Number(event.target.value) })}
            />
          </label>
        </div>
      ) : null}

      {selectedPrice ? (
        <div className="pricing-strip">
          <span>Input ${selectedPrice.inputPerMillion}/1M</span>
          <span>Cached ${selectedPrice.cachedInputPerMillion}/1M</span>
          <span>Output ${selectedPrice.outputPerMillion}/1M</span>
        </div>
      ) : null}

      {message ? <p className="success-message">{message}</p> : null}
      {canManage ? (
        <button className="primary-button" disabled={saving || busy}>
          {saving ? "Saving..." : "Save AI settings"}
        </button>
      ) : null}
    </form>
  );
}
