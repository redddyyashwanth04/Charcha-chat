import { useEffect, useRef } from "react";
import Message from "./Message";

export default function MessageList({
  messages,
  streaming,
  openMsgId,
  onRegenerate,
  onOpenDoubts,
  onSelect,
}) {
  const scroller = useRef(null);
  const stick = useRef(true);

  const onScroll = () => {
    const el = scroller.current;
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 140;
  };

  useEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  return (
    <div className="scroll" ref={scroller} onScroll={onScroll}>
      <div className="thread">
        {messages.map((m, i) => (
          <Message
            key={m.id}
            message={m}
            isLast={i === messages.length - 1}
            streaming={streaming}
            focused={m.id === openMsgId}
            onRegenerate={onRegenerate}
            onOpenDoubts={() => onOpenDoubts(m.id)}
            onSelect={onSelect(m)}
          />
        ))}
      </div>
    </div>
  );
}
