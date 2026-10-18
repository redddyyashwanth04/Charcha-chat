import { useState } from "react";
import Markdown from "./Markdown";

const isSaved = (id) => typeof id === "number";

export default function Message({
  message,
  isLast,
  streaming,
  focused,
  onRegenerate,
  onOpenDoubts,
  onSelect,
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked */
    }
  };

  if (message.role === "user") {
    return (
      <div className="msg user" id={`msg-${message.id}`}>
        <div className="bubble">{message.content}</div>
      </div>
    );
  }

  const live = streaming && isLast;
  return (
    <div className={"msg assistant" + (focused ? " focused" : "")} id={`msg-${message.id}`}>
      <div className="prose" onMouseUp={isSaved(message.id) ? onSelect : undefined}>
        {message.content ? (
          <Markdown>{message.content}</Markdown>
        ) : (
          <span className="thinking" aria-live="polite">
            <i />
            <i />
            <i />
          </span>
        )}
      </div>
      {!live && message.content && (
        <div className="actions">
          <button className="chip" onClick={copy} aria-label="Copy reply">
            {copied ? "Copied" : "Copy"}
          </button>
          {isLast && (
            <button className="chip" onClick={onRegenerate} aria-label="Regenerate reply">
              Retry
            </button>
          )}
          {isSaved(message.id) && (
            <button className="chip accent" onClick={onOpenDoubts}>
              Doubts{message.thread_count > 0 ? ` · ${message.thread_count}` : ""}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
