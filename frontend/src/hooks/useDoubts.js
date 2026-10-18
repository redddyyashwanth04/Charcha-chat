import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../api";

const TMP = "tmp";

/**
 * All doubt threads for ONE assistant reply. Threads form a tree (nested doubts).
 * activeId === null means "composing a brand-new thread".
 */
export function useDoubts(messageId, onCount) {
  const [threads, setThreads] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [activeId, setActiveId] = useState(null);
  const [draft, setDraft] = useState({ quote: "", parentId: null });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const abortRef = useRef(null);

  useEffect(() => {
    let alive = true;
    api
      .getThreads(messageId)
      .then((rows) => {
        if (!alive) return;
        setThreads(rows);
        setLoaded(true);
      })
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
      abortRef.current?.abort();
    };
  }, [messageId]);

  useEffect(() => {
    if (loaded) onCount?.(messageId, threads.filter((t) => t.id !== TMP).length);
  }, [threads, loaded, messageId, onCount]);

  const startNew = useCallback((quote = "", parentId = null) => {
    setActiveId(null);
    setDraft({ quote, parentId });
    setError("");
  }, []);

  const open = useCallback((id) => {
    setActiveId(id);
    setError("");
  }, []);

  const send = useCallback(
    async (question) => {
      if (busy) return;
      const isNew = activeId === null;
      let tid = isNew ? TMP : activeId;
      const stamp = Date.now();
      const userMsg = { id: `u${stamp}`, role: "user", content: question };
      const aiMsg = { id: `a${stamp}`, role: "assistant", content: "" };
      const edit = (fn) => setThreads((list) => list.map((t) => (t.id === tid ? fn(t) : t)));

      if (isNew) {
        const parent = threads.find((t) => t.id === draft.parentId);
        setThreads((list) => [
          ...list,
          {
            id: TMP,
            parent_thread_id: draft.parentId,
            quote: draft.quote || null,
            depth: parent ? parent.depth + 1 : 1,
            messages: [userMsg, aiMsg],
          },
        ]);
        setActiveId(TMP);
      } else {
        edit((t) => ({ ...t, messages: [...t.messages, userMsg, aiMsg] }));
      }

      setBusy(true);
      setError("");
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await api.stream(
          `/messages/${messageId}/doubts`,
          {
            thread_id: isNew ? null : activeId,
            parent_thread_id: isNew ? draft.parentId : null,
            question,
            quote: isNew ? draft.quote || null : null,
          },
          (ev) => {
            if (ev.type === "thread") {
              const old = tid;
              tid = ev.id;
              setThreads((list) => list.map((t) => (t.id === old ? { ...t, id: ev.id } : t)));
              setActiveId(ev.id);
            } else if (ev.type === "delta") {
              edit((t) => ({
                ...t,
                messages: t.messages.map((m) =>
                  m.id === aiMsg.id ? { ...m, content: m.content + ev.text } : m
                ),
              }));
            } else if (ev.type === "error") {
              throw new Error(ev.message);
            }
          },
          controller.signal
        );
      } catch (e) {
        if (e.name !== "AbortError") {
          setError(e.message);
          edit((t) => ({
            ...t,
            messages: t.messages.filter((m) => m.id !== aiMsg.id || m.content),
          }));
        }
      } finally {
        setBusy(false);
      }
    },
    [busy, activeId, draft, messageId, threads]
  );

  const removeThread = useCallback(async (id) => {
    await api.deleteThread(id);
    setThreads((list) => {
      // drop the thread and all of its descendants
      const gone = new Set([id]);
      let grew = true;
      while (grew) {
        grew = false;
        for (const t of list) {
          if (!gone.has(t.id) && gone.has(t.parent_thread_id)) {
            gone.add(t.id);
            grew = true;
          }
        }
      }
      return list.filter((t) => !gone.has(t.id));
    });
    setActiveId(null);
    setDraft({ quote: "", parentId: null });
  }, []);

  return {
    threads,
    loaded,
    activeId,
    draft,
    setDraft,
    busy,
    error,
    startNew,
    open,
    send,
    removeThread,
  };
}
