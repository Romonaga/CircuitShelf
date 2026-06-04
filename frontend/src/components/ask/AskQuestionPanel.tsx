import type { FormEvent } from "react";
import type { ConversationSummary } from "../../types";
import { ConversationPanel } from "../ConversationPanel";
import { ErrorMessage } from "../ErrorMessage";
import { SectionHeader } from "../SectionHeader";

export function AskQuestionPanel({
  activeConversationId,
  askButtonText,
  canSubmit,
  conversations,
  conversationsBusy,
  error,
  question,
  onDeleteConversation,
  onNewConversation,
  onQuestionChange,
  onSelectConversation,
  onSubmit
}: {
  activeConversationId: string | null;
  askButtonText: string;
  canSubmit: boolean;
  conversations: ConversationSummary[];
  conversationsBusy: boolean;
  error: string;
  question: string;
  onDeleteConversation: (conversationId: string) => void;
  onNewConversation: () => void;
  onQuestionChange: (question: string) => void;
  onSelectConversation: (conversationId: string) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <form className="query-panel" onSubmit={onSubmit}>
      <SectionHeader
        title="Ask the shelf"
        description="Grounded answers from indexed books, datasheets, notes, OCR text, and images."
      />
      <ConversationPanel
        conversations={conversations}
        activeConversationId={activeConversationId}
        loading={conversationsBusy}
        onNew={onNewConversation}
        onSelect={onSelectConversation}
        onDelete={onDeleteConversation}
        className="ask-conversation-panel"
      />
      <textarea
        value={question}
        onChange={(event) => onQuestionChange(event.target.value)}
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
  );
}
