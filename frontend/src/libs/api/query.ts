import type { ConversationDetail, ConversationSummary, QueryRequest, QueryResponse } from "../../types";
import { requestJson } from "./core";

export function runQuery(payload: QueryRequest): Promise<QueryResponse> {
  return requestJson<QueryResponse>("/api/query", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getConversations(): Promise<{ conversations: ConversationSummary[] }> {
  return requestJson<{ conversations: ConversationSummary[] }>("/api/conversations");
}

export function createConversation(title = "New conversation"): Promise<{ conversation: ConversationDetail }> {
  return requestJson<{ conversation: ConversationDetail }>("/api/conversations", {
    method: "POST",
    body: JSON.stringify({ title })
  });
}

export function getConversation(conversationId: string): Promise<{ conversation: ConversationDetail }> {
  return requestJson<{ conversation: ConversationDetail }>(`/api/conversations/${encodeURIComponent(conversationId)}`);
}

export function deleteConversation(conversationId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE"
  });
}
