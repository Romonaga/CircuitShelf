import { FormEvent, useCallback, useEffect, useState } from "react";
import { deleteConversation, getConversation, getConversations, getUserPreference, runQuery, updateUserPreference } from "../api";
import type { AppConfig, ChatTurn, ConversationSummary, QueryOptions, QueryResponse } from "../types";
import { errorMessage } from "../lib/errors";
import { formatNumber } from "../lib/format";
import { AnswerRenderer } from "./AnswerRenderer";
import { BuildCard } from "./BuildCard";
import { ChatHistory } from "./ChatHistory";
import { ConversationPanel } from "./ConversationPanel";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";
import { SourceList } from "./SourceList";

const ASK_RETRIEVAL_PREFERENCE_KEY = "ask.retrieval";

export function AskView({ config }: { config: AppConfig }) {
  const [question, setQuestion] = useState("");
  const [model, setModel] = useState(config.defaultModel);
  const [options, setOptions] = useState<QueryOptions>(config.defaults);
  const [chatHistory, setChatHistory] = useState<ChatTurn[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationsBusy, setConversationsBusy] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState("");

  const canSubmit = question.trim().length > 0 && !busy;
  const askButtonText = busy ? `Running ${formatElapsed(elapsedSeconds)}` : "Ask";

  const loadConversations = useCallback(async () => {
    setConversationsBusy(true);
    try {
      const response = await getConversations();
      setConversations(response.conversations);
    } catch (err) {
      setError(errorMessage(err, "Could not load conversations"));
    } finally {
      setConversationsBusy(false);
    }
  }, []);

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    let cancelled = false;
    async function loadPreferences() {
      try {
        const response = await getUserPreference<Partial<QueryOptions>>(ASK_RETRIEVAL_PREFERENCE_KEY);
        if (cancelled) {
          return;
        }
        setOptions((current) => ({
          ...current,
          showFullText: typeof response.value?.showFullText === "boolean" ? response.value.showFullText : current.showFullText,
          bypassCache: typeof response.value?.bypassCache === "boolean" ? response.value.bypassCache : current.bypassCache
        }));
      } catch {
        // Preferences are not required for asking; defaults remain usable.
      } finally {
        if (!cancelled) {
          setPreferencesLoaded(true);
        }
      }
    }
    void loadPreferences();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!preferencesLoaded) {
      return;
    }
    void updateUserPreference(ASK_RETRIEVAL_PREFERENCE_KEY, {
      showFullText: options.showFullText,
      bypassCache: options.bypassCache
    }).catch(() => undefined);
  }, [options.bypassCache, options.showFullText, preferencesLoaded]);

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
        chatHistory,
        conversationId: activeConversationId
      });
      setResult(response);
      setChatHistory(response.chatHistory);
      if (response.conversation?.id) {
        setActiveConversationId(response.conversation.id);
      }
      void loadConversations();
      setQuestion("");
    } catch (err) {
      setError(errorMessage(err, "Query failed"));
    } finally {
      setBusy(false);
    }
  }

  async function selectConversation(conversationId: string) {
    setError("");
    setBusy(true);
    try {
      const response = await getConversation(conversationId);
      const turns = response.conversation.turns.map((turn) => [turn.question, turn.answer] as ChatTurn);
      const lastTurn = response.conversation.turns.at(-1);
      setActiveConversationId(response.conversation.id);
      setChatHistory(turns);
      setResult(
        lastTurn
          ? {
              conversation: response.conversation,
              question: lastTurn.question,
              answer: lastTurn.answer,
              chatHistory: turns,
              sources: [],
              buildCard: null,
              cacheStats: null,
              confidence: lastTurn.confidence ?? null,
              averageQueryTime: null
            }
          : null
      );
    } catch (err) {
      setError(errorMessage(err, "Could not load conversation"));
    } finally {
      setBusy(false);
    }
  }

  async function removeConversation(conversationId: string) {
    setError("");
    try {
      await deleteConversation(conversationId);
      if (conversationId === activeConversationId) {
        startNewConversation();
      }
      await loadConversations();
    } catch (err) {
      setError(errorMessage(err, "Could not remove conversation"));
    }
  }

  function startNewConversation() {
    setActiveConversationId(null);
    setChatHistory([]);
    setResult(null);
    setQuestion("");
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
            onClick={startNewConversation}
          >
            New conversation
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
        <ConversationPanel
          conversations={conversations}
          activeConversationId={activeConversationId}
          loading={conversationsBusy}
          onNew={startNewConversation}
          onSelect={selectConversation}
          onDelete={removeConversation}
        />
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
