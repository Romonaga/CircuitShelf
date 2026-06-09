import type { ChatTurn } from "../types";
import { AnswerRenderer } from "./AnswerRenderer";

export function ChatHistory({ turns }: { turns: ChatTurn[] }) {
  if (!turns.length) {
    return <div className="empty-state compact">No earlier turns in this conversation.</div>;
  }

  return (
    <div className="chat-history">
      {turns.map(([question, answer], index) => (
        <article className="chat-turn" key={`${question}-${index}`}>
          <div className="chat-question">
            <span className="chat-turn-label">Question</span>
            <p>{question}</p>
          </div>
          <div className="chat-answer">
            <span className="chat-turn-label">Answer</span>
            <AnswerRenderer content={answer} />
          </div>
        </article>
      ))}
    </div>
  );
}
