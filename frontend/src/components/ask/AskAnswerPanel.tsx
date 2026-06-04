import type { QueryResponse } from "../../types";
import { formatNumber } from "../../libs/format";
import { AnswerRenderer } from "../AnswerRenderer";
import { BuildCard } from "../BuildCard";
import { ResponseValidationPanel } from "../ResponseValidationPanel";
import { SectionHeader } from "../SectionHeader";

export function AskAnswerPanel({ result }: { result: QueryResponse | null }) {
  return (
    <section className="answer-panel">
      <SectionHeader
        title="Answer"
        description={`Confidence ${formatNumber(result?.confidence)} | Average ${formatNumber(result?.averageQueryTime)}s`}
      />
      <ResponseValidationPanel validation={result?.validation} />
      <BuildCard card={result?.buildCard} />
      <div className={result?.answer ? "answer-text" : "empty-state"}>
        {result?.answer ? <AnswerRenderer content={result.answer} /> : "Ask a question to see the generated answer."}
      </div>
    </section>
  );
}
