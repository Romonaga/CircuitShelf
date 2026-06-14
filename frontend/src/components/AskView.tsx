import { useAskController } from "../hooks/useAskController";
import type { AppConfig, View } from "../types";
import { AskAnswerPanel } from "./ask/AskAnswerPanel";
import { AskConversationHistoryPanel } from "./ask/AskConversationHistoryPanel";
import { AskQuestionPanel } from "./ask/AskQuestionPanel";
import { AskSourcesPanel } from "./ask/AskSourcesPanel";

export function AskView({ config, isActive, setActiveView }: { config: AppConfig; isActive: boolean; setActiveView: (view: View) => void }) {
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

      <AskAnswerPanel
        result={ask.result}
        canCreateBenchProject={Boolean(ask.activeConversationId && ask.result?.answer)}
        creatingBenchProject={ask.promoteBusy}
        createBenchProjectMessage={ask.promoteMessage}
        onCreateBenchProject={() => void ask.createBenchProjectFromConversation(() => setActiveView("bench"))}
      />
      <AskConversationHistoryPanel chatHistory={ask.chatHistory} />
      <AskSourcesPanel sources={ask.result?.sources ?? []} />
    </section>
  );
}
