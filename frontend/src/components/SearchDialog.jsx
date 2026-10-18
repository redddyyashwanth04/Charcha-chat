import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../api";
import { Modal } from "./Modal";

export default function SearchDialog({ chats, onClose }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState([]);
  const [busy, setBusy] = useState(false);
  const [cursor, setCursor] = useState(0);
  const seq = useRef(0);

  useEffect(() => {
    const term = q.trim();
    if (!term) {
      setHits([]);
      return;
    }
    const mine = ++seq.current;
    setBusy(true);
    const t = setTimeout(async () => {
      try {
        const rows = await api.search(term);
        if (mine === seq.current) {
          setHits(rows);
          setCursor(0);
        }
      } catch {
        if (mine === seq.current) setHits([]);
      } finally {
        if (mine === seq.current) setBusy(false);
      }
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  const items = q.trim()
    ? hits.map((h) => ({
        key: `${h.kind}-${h.message_id}-${h.thread_id ?? 0}`,
        title: h.conversation_title,
        snippet: h.snippet,
        tag: h.kind === "doubt" ? "Doubt" : null,
        path: `/c/${h.conversation_id}?m=${h.message_id}${h.thread_id ? `&t=${h.thread_id}` : ""}`,
      }))
    : chats.slice(0, 8).map((c) => ({
        key: `c-${c.id}`,
        title: c.title,
        snippet: null,
        tag: null,
        path: `/c/${c.id}`,
      }));

  const choose = (item) => {
    if (!item) return;
    navigate(item.path);
    onClose();
  };

  const onKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => Math.min(c + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    } else if (e.key === "Enter") {
      choose(items[cursor]);
    }
  };

  return (
    <Modal title="Search chats" onClose={onClose} wide>
      <input
        className="search-input"
        autoFocus
        value={q}
        placeholder="Search your chats and doubts…"
        aria-label="Search chats"
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <ul className="results" role="listbox">
        {!q.trim() && <li className="results-label">Recent</li>}
        {items.map((it, i) => (
          <li key={it.key} role="option" aria-selected={i === cursor}>
            <button
              className={"result" + (i === cursor ? " active" : "")}
              onMouseEnter={() => setCursor(i)}
              onClick={() => choose(it)}
            >
              <span className="result-title">
                {it.title}
                {it.tag && <em className="tag">{it.tag}</em>}
              </span>
              {it.snippet && <span className="muted small">{it.snippet}</span>}
            </button>
          </li>
        ))}
        {q.trim() && !busy && items.length === 0 && <li className="muted pad">No results.</li>}
        {busy && <li className="muted pad">Searching…</li>}
      </ul>
    </Modal>
  );
}
