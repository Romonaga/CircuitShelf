import { FormEvent, useCallback, useEffect, useState } from "react";
import { deleteConversation, getConversation, getConversations, getUserPreference, runQuery } from "../api";
import type { AppConfig, ChatTurn, ConversationSummary, QueryOptions, QueryResponse } from "../types";
import { errorMessage } from "../lib/errors";
import { formatNumber } from "../lib/format";
import { formatElapsed } from "../lib/time";
import { ASK_RETRIEVAL_PREFERENCE_KEY, resolveAskPreferences, type AskRetrievalPreference } from "../lib/askPreferences";
import { useElapsedSeconds } from "../hooks/useElapsedSeconds";
import { AnswerRenderer } from "./AnswerRenderer";
import { BuildCard } from "./BuildCard";
import { ChatHistory } from "./ChatHistory";
import { ConversationPanel } from "./ConversationPanel";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";
import { SourceList } from "./SourceList";
import { ResponseValidationPanel } from "./ResponseValidationPanel";

export function AskView({ config, isActive }: { config: AppConfig; isActive: boolean }) {
  const [question, setQuestion] = useState("");
  const [model, setModel] = useState(config.defaultModel);
  const [options, setOptions] = useState<QueryOptions>(config.defaults);
  const [chatHistory, setChatHistory] = useState<ChatTurn[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationsBusy, setConversationsBusy] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const elapsedSeconds = useElapsedSeconds(busy);
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
      if (!isActive) {
        return;
      }
      try {
        const response = await getUserPreference<AskRetrievalPreference>(ASK_RETRIEVAL_PREFERENCE_KEY);
        if (cancelled) {
          return;
        }
        const resolved = resolveAskPreferences(config, response.value);
        setModel(resolved.model);
        setOptions(resolved.options);
      } catch {
        // Preferences are not required for asking; defaults remain usable.
      }
    }
    void loadPreferences();
    return () => {
      cancelled = true;
    };
  }, [config, isActive]);

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
              validation: null,
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
        <ConversationPanel
          conversations={conversations}
          activeConversationId={activeConversationId}
          loading={conversationsBusy}
          onNew={startNewConversation}
          onSelect={selectConversation}
          onDelete={removeConversation}
          className="ask-conversation-panel"
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
        </div>
        <ErrorMessage message={error} />
      </form>

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
