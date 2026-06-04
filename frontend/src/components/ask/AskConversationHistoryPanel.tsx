import type { ChatTurn } from "../../types";
import { ChatHistory } from "../ChatHistory";
import { SectionHeader } from "../SectionHeader";

export function AskConversationHistoryPanel({ chatHistory }: { chatHistory: ChatTurn[] }) {
  return (
    <section className="history-panel">
      <SectionHeader title="Conversation" description={`${Math.max(chatHistory.length - 1, 0)} earlier turns`} />
      <ChatHistory turns={chatHistory.slice(0, -1)} />
    </section>
  );
}
