import { FormEvent, useEffect, useState } from "react";
import { runQuery } from "../api";
import type { AppConfig, ChatTurn, QueryOptions, QueryResponse } from "../types";
import { errorMessage } from "../lib/errors";
import { formatNumber } from "../lib/format";
import { AnswerRenderer } from "./AnswerRenderer";
import { BuildCard } from "./BuildCard";
import { ChatHistory } from "./ChatHistory";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";
import { SourceList } from "./SourceList";

export function AskView({ config }: { config: AppConfig }) {
  const [question, setQuestion] = useState("");
  const [model, setModel] = useState(config.defaultModel);
  const [options, setOptions] = useState<QueryOptions>(config.defaults);
  const [chatHistory, setChatHistory] = useState<ChatTurn[]>([]);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState("");

  const canSubmit = question.trim().length > 0 && !busy;
  const askButtonText = busy ? `Running ${formatElapsed(elapsedSeconds)}` : "Ask";

  useEffect(() => {
    if (!busy) {
      setElapsedSeconds(0);
      return;
    }

    const startedAt = Date.now();
    setElapsedSeconds(0);
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [busy]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await runQuery({
        ...options,
        question,
        model,
        chatHistory
      });
      setResult(response);
      setChatHistory(response.chatHistory);
      setQuestion("");
    } catch (err) {
      setError(errorMessage(err, "Query failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="view-grid ask-grid">
      <form className="query-panel" onSubmit={submit}>
        <SectionHeader
          title="Ask the shelf"
          description="Grounded answers from indexed books, datasheets, notes, OCR text, and images."
        />
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Example: Wire a 555 timer in astable mode and explain every pin connection."
          rows={7}
        />
        <div className="query-actions">
          <button className="primary-button" disabled={!canSubmit}>
            {askButtonText}
          </button>
          <button
            className="ghost-button"
            type="button"
            onClick={() => {
              setChatHistory([]);
              setResult(null);
            }}
          >
            Clear
          </button>
        </div>
        <ErrorMessage message={error} />
      </form>

      <aside className="controls-panel">
        <h3>Retrieval</h3>
        <label>
          Model
          <select value={model} onChange={(event) => setModel(event.target.value)}>
            {config.models.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          Strategy
          <select value={options.strategy} onChange={(event) => setOptions({ ...options, strategy: event.target.value })}>
            {config.retrievalStrategies.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          Top K
          <input
            type="number"
            min="1"
            max="80"
            value={options.topK}
            onChange={(event) => setOptions({ ...options, topK: Number(event.target.value) })}
          />
        </label>
        <label>
          Distance threshold
          <input
            type="number"
            step="0.1"
            min="0.1"
            value={options.distanceThreshold}
            onChange={(event) => setOptions({ ...options, distanceThreshold: Number(event.target.value) })}
          />
        </label>
        <label>
          Context tokens
          <input
            type="number"
            min="100"
            step="100"
            value={options.maxTokens}
            onChange={(event) => setOptions({ ...options, maxTokens: Number(event.target.value) })}
          />
        </label>
        <label className="check-row">
          <input
            type="checkbox"
            checked={options.showFullText}
            onChange={(event) => setOptions({ ...options, showFullText: event.target.checked })}
          />
          Show full source text
        </label>
        <label className="check-row">
          <input
            type="checkbox"
            checked={options.bypassCache}
            onChange={(event) => setOptions({ ...options, bypassCache: event.target.checked })}
          />
          Bypass cache
        </label>
      </aside>

      <section className="answer-panel">
        <SectionHeader
          title="Answer"
          description={`Confidence ${formatNumber(result?.confidence)} | Average ${formatNumber(result?.averageQueryTime)}s`}
        />
        <BuildCard card={result?.buildCard} />
        <div className={result?.answer ? "answer-text" : "empty-state"}>
          {result?.answer ? <AnswerRenderer content={result.answer} /> : "Ask a question to see the generated answer."}
        </div>
      </section>

      <section className="history-panel">
        <SectionHeader title="Conversation" description={`${Math.max(chatHistory.length - 1, 0)} earlier turns`} />
        <ChatHistory turns={chatHistory.slice(0, -1)} />
      </section>

      <section className="sources-panel">
        <h3>Sources</h3>
        <SourceList sources={result?.sources ?? []} />
      </section>
    </section>
  );
}

function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes <= 0) {
    return `${remainingSeconds}s`;
  }
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}
