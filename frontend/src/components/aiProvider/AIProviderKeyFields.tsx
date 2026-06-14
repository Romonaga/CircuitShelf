import type { AIProviderSettings } from "../../types";

export function AIProviderKeyFields({
  apiKey,
  canManage,
  clearApiKey,
  settings,
  title = settings.hasApiKey ? "Key stored" : "No key stored",
  preview = settings.keyPreview,
  emptyText = "Paste a key to store it encrypted.",
  replaceLabel = "Replace key",
  clearLabel = "Clear stored key",
  placeholder = "sk-...",
  onApiKeyChange,
  onClearApiKeyChange
}: {
  apiKey: string;
  canManage: boolean;
  clearApiKey: boolean;
  settings: AIProviderSettings;
  title?: string;
  preview?: string;
  emptyText?: string;
  replaceLabel?: string;
  clearLabel?: string;
  placeholder?: string;
  onApiKeyChange: (value: string) => void;
  onClearApiKeyChange: (value: boolean) => void;
}) {
  return (
    <div className="ai-key-row">
      <div>
        <strong>{title}</strong>
        <span>{preview || emptyText}</span>
      </div>
      <label>
        {replaceLabel}
        <input
          type="password"
          value={apiKey}
          disabled={!canManage || clearApiKey}
          onChange={(event) => onApiKeyChange(event.target.value)}
          autoComplete="off"
          placeholder={placeholder}
        />
      </label>
      <label className="inline-check">
        <input
          type="checkbox"
          checked={clearApiKey}
          disabled={!canManage}
          onChange={(event) => onClearApiKeyChange(event.target.checked)}
        />
        {clearLabel}
      </label>
    </div>
  );
}
