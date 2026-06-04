import type { CircuitBuildCard } from "../types";
import { formatNumber } from "../libs/format";

export function BuildCard({ card }: { card?: CircuitBuildCard | null }) {
  if (!card) {
    return null;
  }

  return (
    <section className="build-card">
      <div className="build-card-heading">
        <div>
          <h3>{card.title}</h3>
          <p>
            {card.componentType} | Confidence {formatNumber(card.confidence)}
          </p>
        </div>
      </div>

      <div className="build-card-grid">
        <section>
          <h4>Parts</h4>
          <ul>
            {card.parts.map((part) => (
              <li key={part.name}>
                <strong>{part.name}</strong>
                <span>{part.detail}</span>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h4>Power</h4>
          <ul>
            {card.power.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>

      <section>
        <h4>Pin-by-pin wiring</h4>
        <div className="build-wiring-table">
          {card.wiring.map((row) => (
            <div key={`${row.from}-${row.to}`} className="build-wiring-row">
              <strong>{row.from}</strong>
              <span>{row.to}</span>
              <small>
                {row.note}
                {row.page ? ` Page ${row.page}.` : ""}
              </small>
            </div>
          ))}
        </div>
      </section>

      <div className="build-card-grid">
        <section>
          <h4>Checks</h4>
          <ul>
            {card.checks.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section>
          <h4>Warnings</h4>
          <ul>
            {card.warnings.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>
    </section>
  );
}
