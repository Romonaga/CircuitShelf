import type { ConversationSummary } from "../types";
import { formatInteger } from "../lib/format";

export function ConversationPanel({
  conversations,
  activeConversationId,
  loading,
  onNew,
  onSelect,
  onDelete,
  className = ""
}: {
  conversations: ConversationSummary[];
  activeConversationId?: string | null;
  loading: boolean;
  onNew: () => void;
  onSelect: (conversationId: string) => void;
  onDelete: (conversationId: string) => void;
  className?: string;
}) {
  return (
    <div className={["conversation-panel", className].filter(Boolean).join(" ")}>
      <div className="conversation-toolbar">
        <h3>Conversations</h3>
        <button className="ghost-button compact-button" type="button" onClick={onNew}>
          New
        </button>
      </div>
      <div className="conversation-list">
        {conversations.map((conversation) => (
          <div
            key={conversation.id}
            className={conversation.id === activeConversationId ? "conversation-row active" : "conversation-row"}
          >
            <button type="button" onClick={() => onSelect(conversation.id)}>
              <strong>{conversation.title}</strong>
              <small>
                {formatInteger(conversation.turnCount)} turns
                {conversation.updatedAt ? ` | ${new Date(conversation.updatedAt).toLocaleString()}` : ""}
              </small>
            </button>
            <button
              className="ghost-button danger-button compact-button"
              type="button"
              onClick={() => onDelete(conversation.id)}
              title="Remove conversation"
            >
              Remove
            </button>
          </div>
        ))}
        {!conversations.length ? (
          <div className="empty-state compact">{loading ? "Loading conversations..." : "No saved conversations yet."}</div>
        ) : null}
      </div>
    </div>
  );
}
