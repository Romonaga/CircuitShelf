import { formatInteger, formatNumber } from "../../libs/format";
import type { RuntimeCatalog } from "../../types";
import { SectionHeader } from "../SectionHeader";

export function RuntimeModelTable({ models }: { models: RuntimeCatalog["llmModels"] }) {
  return (
    <section className="runtime-panel">
      <SectionHeader title="LLM models" description="Local model options and default generation settings." />
      <div className="runtime-table runtime-model-table">
        <div className="runtime-table-head">
          <span>Model</span>
          <span>Provider</span>
          <span>Status</span>
          <span>Temp</span>
          <span>Predict</span>
          <span>Context</span>
        </div>
        {models.map((model) => (
          <div className="runtime-table-row" key={model.id}>
            <strong>{model.displayName || model.modelName}</strong>
            <span>{model.provider}</span>
            <span>{model.isDefault ? "Default" : model.isEnabled ? "Enabled" : "Disabled"}</span>
            <span>{formatNumber(model.temperature)}</span>
            <span>{formatInteger(model.numPredict)}</span>
            <span>{model.numCtx ? formatInteger(model.numCtx) : "default"}</span>
          </div>
        ))}
        {models.length === 0 ? <div className="empty-state compact">No LLM models are registered.</div> : null}
      </div>
    </section>
  );
}
