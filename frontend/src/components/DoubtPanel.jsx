import { useEffect, useMemo, useRef, useState } from "react";
import AskFab from "./AskFab";
import Markdown from "./Markdown";
import { useAskSelection } from "../hooks/useAskSelection";
import { useDoubts } from "../hooks/useDoubts";

const MAX_DEPTH = 3; // keep in sync with MAX_DOUBT_DEPTH on the backend
const clip = (s, n) => (s.length > n ? s.slice(0, n).trimEnd() + "…" : s);

const labelOf = (t) =>
  t.quote ? `“${clip(t.quote, 48)}”` : clip(t.messages[0]?.content || "Doubt", 48);

/** Depth-first order so children render right under their parent. */
function flatten(threads) {
  const out = [];
  const walk = (parentId) => {
    for (const t of threads.filter((x) => (x.parent_thread_id ?? null) === parentId)) {
      out.push(t);
      walk(t.id);
    }
  };
  walk(null);
  return out;
}

export default function DoubtPanel({ message, intent, onClose, onCount }) {
  const d = useDoubts(message.id, onCount);
  const { sel, capture, clear } = useAskSelection();
  const [text, setText] = useState("");
  const endRef = useRef(null);
  const inputRef = useRef(null);

  const ordered = useMemo(() => flatten(d.threads), [d.threads]);
  const active = d.threads.find((t) => t.id === d.activeId) || null;
  const crumbs = useMemo(() => {
    const chain = [];
    let node = active;
    while (node) {
      chain.unshift(node);
      node = d.threads.find((t) => t.id === node.parent_thread_id);
    }
    return chain;
  }, [active, d.threads]);

  // choose what to show once threads are loaded (and again whenever a new intent arrives)
  const { loaded, open, startNew } = d;
  useEffect(() => {
    if (!loaded) return;
    if (intent?.threadId) open(intent.threadId);
    else if (intent?.quote) startNew(intent.quote, null);
    else if (d.threads.length) open(d.threads[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, intent, open, startNew]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [active?.messages, d.activeId]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [d.activeId, loaded]);

  const submit = () => {
    const q = text.trim();
    if (!q || d.busy) return;
    setText("");
    d.send(q);
  };

  const askSub = (s) => {
    if (!active || active.depth >= MAX_DEPTH) return clear();
    d.startNew(s.text, active.id);
    clear();
  };

  const canNest = active && active.depth < MAX_DEPTH;

  return (
    <aside className="panel" aria-label="Doubt window">
      <header className="panel-head">
        <div>
          <strong>Doubts</strong>
          <div className="muted small clip" title={message.content}>
            on: {clip(message.content.replace(/[#*`>-]/g, "").trim(), 70)}
          </div>
        </div>
        <button className="btn primary-outline" onClick={onClose}>
          Back to chat
        </button>
      </header>

      <div className="threadbar">
        {ordered.map((t) => (
          <button
            key={t.id}
            className={"thread-chip" + (t.id === d.activeId ? " active" : "")}
            style={{ marginLeft: (t.depth - 1) * 14 }}
            onClick={() => d.open(t.id)}
            title={labelOf(t)}
          >
            {t.depth > 1 ? "↳ " : ""}
            {labelOf(t)}
          </button>
        ))}
        <button className="thread-chip new" onClick={() => d.startNew("", null)}>
          + New doubt
        </button>
      </div>

      <div className="scroll panel-body">
        {crumbs.length > 1 && (
          <nav className="crumbs" aria-label="Doubt path">
            {crumbs.map((c, i) => (
              <span key={c.id}>
                {i > 0 && " › "}
                {i < crumbs.length - 1 ? (
                  <button onClick={() => d.open(c.id)}>{labelOf(c)}</button>
                ) : (
                  <b>{labelOf(c)}</b>
                )}
              </span>
            ))}
          </nav>
        )}

        {!d.loaded && <p className="muted">Loading…</p>}
        {d.loaded && !active && (
          <p className="muted hint">
            Ask as many doubts as you like about this reply. They never touch your main chat. Select
            text in this reply and choose <b>Ask doubt</b> to point at an exact passage.
          </p>
        )}

        {active && (
          <div className="doubt-thread">
            {active.quote && <blockquote>{active.quote}</blockquote>}
            {active.messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="msg user">
                  <div className="bubble">{m.content}</div>
                </div>
              ) : (
                <div key={m.id} className="msg assistant">
                  <div className="prose" onMouseUp={m.content ? capture({}) : undefined}>
                    {m.content ? (
                      <Markdown>{m.content}</Markdown>
                    ) : (
                      <span className="thinking">
                        <i />
                        <i />
                        <i />
                      </span>
                    )}
                  </div>
                </div>
              )
            )}
            {d.activeId !== "tmp" && (
              <div className="thread-tools">
                {canNest && (
                  <span className="muted small">Select text above to ask a sub-doubt.</span>
                )}
                <button className="link danger-text" onClick={() => d.removeThread(active.id)}>
                  Delete thread
                </button>
              </div>
            )}
          </div>
        )}
        {d.error && (
          <div className="inline-error" role="alert">
            {d.error}
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="composer panel-composer">
        {!active && d.draft.quote && (
          <blockquote className="pending">
            <span>{clip(d.draft.quote, 160)}</span>
            <button
              className="x"
              aria-label="Remove quoted passage"
              onClick={() => d.setDraft({ ...d.draft, quote: "" })}
            >
              ×
            </button>
          </blockquote>
        )}
        <div className="composer-box">
          <textarea
            ref={inputRef}
            rows={1}
            value={text}
            aria-label="Your doubt"
            placeholder={active ? "Ask a follow-up…" : "What's confusing?"}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <button
            className="send"
            onClick={submit}
            disabled={!text.trim() || d.busy}
            aria-label="Ask doubt"
          >
            ↑
          </button>
        </div>
      </div>
      <AskFab sel={canNest ? sel : null} onAsk={askSub} />
    </aside>
  );
}
