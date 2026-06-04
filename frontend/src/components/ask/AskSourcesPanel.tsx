import type { SourceSummary } from "../../types";
import { SourceList } from "../SourceList";

export function AskSourcesPanel({ sources }: { sources: SourceSummary[] }) {
  return (
    <section className="sources-panel">
      <h3>Sources</h3>
      <SourceList sources={sources} />
    </section>
  );
}
