import type { AIModelPricing, AIModelPricingOverride } from "../types";
import { formatNumber } from "../lib/format";

function overrideFor(modelName: string, overrides: AIModelPricingOverride[]) {
  return overrides.find((override) => override.modelName === modelName);
}

function withoutModel(modelName: string, overrides: AIModelPricingOverride[]) {
  return overrides.filter((override) => override.modelName !== modelName);
}

export function AIProviderPricingOverrides({
  pricing,
  overrides,
  disabled,
  onChange
}: {
  pricing: AIModelPricing[];
  overrides: AIModelPricingOverride[];
  disabled: boolean;
  onChange: (overrides: AIModelPricingOverride[]) => void;
}) {
  function setEnabled(row: AIModelPricing, enabled: boolean) {
    if (!enabled) {
      onChange(withoutModel(row.modelName, overrides));
      return;
    }
    const existing = overrideFor(row.modelName, overrides);
    if (existing) {
      return;
    }
    onChange([
      ...overrides,
      {
        modelName: row.modelName,
        inputPerMillion: row.inputPerMillion,
        cachedInputPerMillion: row.cachedInputPerMillion,
        outputPerMillion: row.outputPerMillion,
        currency: row.currency || "USD"
      }
    ]);
  }

  function setRate(modelName: string, key: "inputPerMillion" | "cachedInputPerMillion" | "outputPerMillion", value: number) {
    onChange(overrides.map((override) => (
      override.modelName === modelName ? { ...override, [key]: Math.max(0, value) } : override
    )));
  }

  if (!pricing.length) {
    return null;
  }

  return (
    <section className="pricing-override-panel">
      <div className="pricing-override-heading">
        <h3>Cost rates</h3>
        <p>Override catalog pricing for this scope when your actual OpenAI rate differs.</p>
      </div>
      <div className="table-wrap">
        <table className="data-table pricing-override-table">
          <thead>
            <tr>
              <th>Custom</th>
              <th>Model</th>
              <th>Input / 1M</th>
              <th>Cached / 1M</th>
              <th>Output / 1M</th>
            </tr>
          </thead>
          <tbody>
            {pricing.map((row) => {
              const custom = overrideFor(row.modelName, overrides);
              return (
                <tr key={row.modelName}>
                  <td>
                    <input
                      type="checkbox"
                      checked={Boolean(custom)}
                      disabled={disabled}
                      onChange={(event) => setEnabled(row, event.target.checked)}
                    />
                  </td>
                  <td>
                    <strong>{row.modelName}</strong>
                    <small>{custom ? "Using custom rate" : "Catalog rate"}</small>
                  </td>
                  {(["inputPerMillion", "cachedInputPerMillion", "outputPerMillion"] as const).map((key) => (
                    <td key={key}>
                      {custom ? (
                        <input
                          type="number"
                          min={0}
                          step="0.000001"
                          value={custom[key]}
                          disabled={disabled}
                          onChange={(event) => setRate(row.modelName, key, Number(event.target.value))}
                        />
                      ) : (
                        <span>${formatNumber(row[key])}</span>
                      )}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
