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
          <div className="chat-question">{question}</div>
          <div className="chat-answer">
            <AnswerRenderer content={answer} />
          </div>
        </article>
      ))}
    </div>
  );
}
