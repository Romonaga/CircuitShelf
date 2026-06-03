import type { DatasheetFact, DatasheetIntelligence } from "../types";
import { formatInteger, formatNumber } from "../lib/format";

const FACT_LABELS: Record<string, string> = {
  voltage: "Voltage",
  current: "Current",
  package: "Package",
  application: "Applications",
  warning: "Warnings",
  absolute_maximum: "Absolute Maximum"
};

function groupFacts(facts: DatasheetFact[]): Array<{ type: string; facts: DatasheetFact[] }> {
  const grouped = new Map<string, DatasheetFact[]>();
  facts.forEach((fact) => {
    const group = grouped.get(fact.type) ?? [];
    group.push(fact);
    grouped.set(fact.type, group);
  });
  return Array.from(grouped.entries()).map(([type, items]) => ({ type, facts: items }));
}

export function DatasheetIntelligencePanel({ intelligence }: { intelligence?: DatasheetIntelligence | null }) {
  if (!intelligence) {
    return null;
  }

  const groups = groupFacts(intelligence.facts ?? []);
  const pins = intelligence.pinout?.pins ?? [];
  if (!intelligence.componentName && !groups.length && !pins.length) {
    return null;
  }

  return (
    <div className="intelligence-panel">
      <div className="intelligence-heading">
        <div>
          <strong>{intelligence.componentName || intelligence.displayName}</strong>
          <p>
            {intelligence.componentType} | Confidence {formatNumber(intelligence.confidence)}
          </p>
        </div>
      </div>
      {intelligence.summary ? <p className="intelligence-summary">{intelligence.summary}</p> : null}
      {pins.length ? (
        <details className="intelligence-details intelligence-pinout" open>
          <summary>Detected pinout ({formatInteger(pins.length)})</summary>
          <div className="document-pinout-grid">
            {pins.map((pin) => (
              <div key={`${pin.pin}-${pin.function}`} className="document-pin-card">
                <span>Pin {pin.pin}</span>
                <strong>{pin.function || pin.label}</strong>
                {pin.label && pin.label !== pin.function ? <small>{pin.label}</small> : null}
                {pin.page ? <small>Page {pin.page}</small> : null}
              </div>
            ))}
          </div>
        </details>
      ) : null}
      {groups.length ? (
        <details className="intelligence-details" open>
          <summary>Facts ({formatInteger(groups.reduce((total, group) => total + group.facts.length, 0))})</summary>
          <div className="intelligence-facts">
            {groups.map((group) => (
              <section key={group.type}>
                <h4>{FACT_LABELS[group.type] ?? group.type}</h4>
                <div className="fact-list">
                  {group.facts.slice(0, 6).map((fact) => (
                    <div key={`${fact.type}-${fact.label}-${fact.value}-${fact.page}`} className="fact-row">
                      <span>{fact.label}</span>
                      <strong>
                        {fact.value}
                        {fact.unit ? ` ${fact.unit}` : ""}
                      </strong>
                      {fact.page ? <small>Page {fact.page}</small> : null}
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}
