import type { CodeSampleInfo } from "../types";

function joinLabel(values: string[]): string {
  return values.filter(Boolean).join(", ");
}

function TagList({ values }: { values: string[] }) {
  const items = values.filter(Boolean);
  if (!items.length) {
    return <span className="code-sample-empty">None detected</span>;
  }
  return (
    <div className="code-sample-tags">
      {items.map((value) => (
        <span key={value}>{value}</span>
      ))}
    </div>
  );
}

export function CodeSamplePanel({ codeSample }: { codeSample?: CodeSampleInfo | null }) {
  if (!codeSample) {
    return null;
  }

  const runtime = joinLabel([codeSample.language, codeSample.framework ?? "", codeSample.board ?? ""]);

  return (
    <div className="code-sample-panel">
      <div className="code-sample-heading">
        <div>
          <strong>{codeSample.packDisplayName || codeSample.packKey}</strong>
          <p>{runtime || "Code sample"} | {codeSample.relativePath}</p>
        </div>
        {codeSample.role ? <span>{codeSample.role}</span> : null}
      </div>
      {codeSample.summary ? <p className="code-sample-summary">{codeSample.summary}</p> : null}
      <div className="code-sample-grid">
        <section>
          <h4>Libraries</h4>
          <TagList values={codeSample.libraries} />
        </section>
        <section>
          <h4>Hardware</h4>
          <TagList values={[...codeSample.components, ...codeSample.interfaces]} />
        </section>
      </div>
      {codeSample.pins.length ? (
        <details className="code-sample-details" open>
          <summary>Pin assignments ({codeSample.pins.length})</summary>
          <div className="code-sample-pins">
            {codeSample.pins.map((pin) => (
              <div key={`${pin.name}-${pin.pin}`} className="code-sample-pin-row">
                <span>{pin.name}</span>
                <strong>{pin.pin}</strong>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}
