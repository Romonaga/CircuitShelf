export function AIProviderModelRefresh({
  canManage,
  hasApiKey,
  modelsCount,
  refreshing,
  onRefresh
}: {
  canManage: boolean;
  hasApiKey: boolean;
  modelsCount: number;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className="model-refresh-panel">
      <div>
        <strong>Available models</strong>
        <span>
          {modelsCount
            ? `${modelsCount} models loaded from OpenAI for this key.`
            : "Use the stored key to query the models this account can access."}
        </span>
      </div>
      <button className="ghost-button" type="button" disabled={!canManage || refreshing || !hasApiKey} onClick={onRefresh}>
        {refreshing ? "Refreshing..." : "Refresh from OpenAI"}
      </button>
    </div>
  );
}
