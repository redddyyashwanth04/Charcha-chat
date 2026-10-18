import { useEffect, useRef } from "react";

export default function Composer({
  value,
  onChange,
  onSend,
  onStop,
  streaming,
  placeholder = "Message DoubtChat…",
  autoFocusKey,
}) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [value]);

  useEffect(() => {
    ref.current?.focus();
  }, [autoFocusKey]);

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (!streaming) onSend();
    }
  };

  return (
    <div className="composer">
      <div className="composer-box">
        <textarea
          ref={ref}
          rows={1}
          value={value}
          placeholder={placeholder}
          aria-label="Message"
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
        />
        {streaming ? (
          <button className="send stop" onClick={onStop} aria-label="Stop generating">
            ■
          </button>
        ) : (
          <button
            className="send"
            onClick={onSend}
            disabled={!value.trim()}
            aria-label="Send message"
          >
            ↑
          </button>
        )}
      </div>
      <p className="fineprint">
        Select any text in a reply to ask a doubt without leaving your place.
      </p>
    </div>
  );
}
