import { useAskController } from "../hooks/useAskController";
import type { AppConfig } from "../types";
import { AskAnswerPanel } from "./ask/AskAnswerPanel";
import { AskConversationHistoryPanel } from "./ask/AskConversationHistoryPanel";
import { AskQuestionPanel } from "./ask/AskQuestionPanel";
import { AskSourcesPanel } from "./ask/AskSourcesPanel";

export function AskView({ config, isActive }: { config: AppConfig; isActive: boolean }) {
  const ask = useAskController({ config, isActive });

  return (
    <section className="view-grid ask-grid">
      <AskQuestionPanel
        activeConversationId={ask.activeConversationId}
        askButtonText={ask.askButtonText}
        canSubmit={ask.canSubmit}
        conversations={ask.conversations}
        conversationsBusy={ask.conversationsBusy}
        error={ask.error}
        question={ask.question}
        onDeleteConversation={(conversationId) => void ask.removeConversation(conversationId)}
        onNewConversation={ask.startNewConversation}
        onQuestionChange={ask.setQuestion}
        onSelectConversation={(conversationId) => void ask.selectConversation(conversationId)}
        onSubmit={(event) => void ask.submit(event)}
      />

      <AskAnswerPanel result={ask.result} />
      <AskConversationHistoryPanel chatHistory={ask.chatHistory} />
      <AskSourcesPanel sources={ask.result?.sources ?? []} />
    </section>
  );
}
