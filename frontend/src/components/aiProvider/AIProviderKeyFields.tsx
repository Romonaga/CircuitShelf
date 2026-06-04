import type { AIProviderSettings } from "../../types";

export function AIProviderKeyFields({
  apiKey,
  canManage,
  clearApiKey,
  settings,
  onApiKeyChange,
  onClearApiKeyChange
}: {
  apiKey: string;
  canManage: boolean;
  clearApiKey: boolean;
  settings: AIProviderSettings;
  onApiKeyChange: (value: string) => void;
  onClearApiKeyChange: (value: boolean) => void;
}) {
  return (
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
          onChange={(event) => onApiKeyChange(event.target.value)}
          autoComplete="off"
          placeholder="sk-..."
        />
      </label>
      <label className="inline-check">
        <input
          type="checkbox"
          checked={clearApiKey}
          disabled={!canManage}
          onChange={(event) => onClearApiKeyChange(event.target.checked)}
        />
        Clear stored key
      </label>
    </div>
  );
}
