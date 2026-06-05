import { FormEvent, useCallback, useEffect, useState } from "react";
import { deleteConversation, getConversation, getConversations, getUserPreference, runQuery } from "../libs/api";
import { ASK_RETRIEVAL_PREFERENCE_KEY, resolveAskPreferences, type AskRetrievalPreference } from "../libs/askPreferences";
import { errorMessage } from "../libs/errors";
import { formatElapsed } from "../libs/time";
import type { AppConfig, ChatTurn, ConversationSummary, QueryOptions, QueryResponse } from "../types";
import { useElapsedSeconds } from "./useElapsedSeconds";

function restoreResultFromConversationTurn(
  conversation: QueryResponse["conversation"],
  turns: ChatTurn[],
  turn: NonNullable<QueryResponse["conversation"]>["turns"][number]
): QueryResponse {
  const snapshot = turn.responseSnapshot;
  if (snapshot?.answer) {
    const contextChatHistory = Array.isArray(snapshot.contextChatHistory)
      ? snapshot.contextChatHistory
      : Array.isArray(snapshot.chatHistory)
        ? snapshot.chatHistory
        : turns;
    return {
      conversation,
      question: snapshot.question || turn.question,
      answer: snapshot.answer,
      chatHistory: Array.isArray(snapshot.chatHistory) ? snapshot.chatHistory : turns,
      contextChatHistory,
      sources: Array.isArray(snapshot.sources) ? snapshot.sources : [],
      buildCard: snapshot.buildCard ?? null,
      validation: snapshot.validation ?? null,
      cacheStats: snapshot.cacheStats ?? null,
      confidence: snapshot.confidence ?? turn.confidence ?? null,
      averageQueryTime: snapshot.averageQueryTime ?? null,
      error: snapshot.error
    };
  }

  return {
    conversation,
    question: turn.question,
    answer: turn.answer,
    chatHistory: turns,
    contextChatHistory: turns,
    sources: [],
    buildCard: null,
    validation: null,
    cacheStats: null,
    confidence: turn.confidence ?? null,
    averageQueryTime: null
  };
}

export function useAskController({ config, isActive }: { config: AppConfig; isActive: boolean }) {
  const [question, setQuestion] = useState("");
  const [model, setModel] = useState(config.defaultModel);
  const [options, setOptions] = useState<QueryOptions>(config.defaults);
  const [chatHistory, setChatHistory] = useState<ChatTurn[]>([]);
  const [contextChatHistory, setContextChatHistory] = useState<ChatTurn[]>([]);
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
        chatHistory: contextChatHistory,
        conversationId: activeConversationId
      });
      setResult(response);
      setChatHistory(response.chatHistory);
      setContextChatHistory(response.contextChatHistory ?? response.chatHistory);
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
      const restoredResult = lastTurn ? restoreResultFromConversationTurn(response.conversation, turns, lastTurn) : null;
      setActiveConversationId(response.conversation.id);
      setChatHistory(restoredResult?.chatHistory ?? turns);
      setContextChatHistory(restoredResult?.contextChatHistory ?? turns);
      setResult(restoredResult);
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
    setContextChatHistory([]);
    setResult(null);
    setQuestion("");
  }

  return {
    activeConversationId,
    askButtonText,
    canSubmit,
    chatHistory,
    conversations,
    conversationsBusy,
    error,
    question,
    result,
    removeConversation,
    selectConversation,
    setQuestion,
    startNewConversation,
    submit
  };
}
