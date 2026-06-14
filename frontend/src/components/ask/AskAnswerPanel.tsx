import type { QueryResponse } from "../../types";
import { formatNumber } from "../../libs/format";
import { AnswerRenderer } from "../AnswerRenderer";
import { BuildCard } from "../BuildCard";
import { ResponseValidationPanel } from "../ResponseValidationPanel";
import { SectionHeader } from "../SectionHeader";

export function AskAnswerPanel({
  result,
  canCreateBenchProject,
  creatingBenchProject,
  createBenchProjectMessage,
  onCreateBenchProject
}: {
  result: QueryResponse | null;
  canCreateBenchProject: boolean;
  creatingBenchProject: boolean;
  createBenchProjectMessage: string;
  onCreateBenchProject: () => void;
}) {
  return (
    <section className="answer-panel">
      <SectionHeader
        title="Answer"
        description={`Confidence ${formatNumber(result?.confidence)} | Average ${formatNumber(result?.averageQueryTime)}s`}
      />
      {result?.answer ? (
        <div className="answer-actions">
          <button type="button" className="secondary-button" disabled={!canCreateBenchProject || creatingBenchProject} onClick={onCreateBenchProject}>
            {creatingBenchProject ? "Creating..." : "Create Bench project"}
          </button>
          {createBenchProjectMessage ? <span>{createBenchProjectMessage}</span> : null}
        </div>
      ) : null}
      <ResponseValidationPanel validation={result?.validation} />
      <BuildCard card={result?.buildCard} />
      <div className={result?.answer ? "answer-text" : "empty-state"}>
        {result?.answer ? <AnswerRenderer content={result.answer} /> : "Ask a question to see the generated answer."}
      </div>
    </section>
  );
}
