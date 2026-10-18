import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import * as api from "../api";
import AskFab from "../components/AskFab";
import Composer from "../components/Composer";
import DoubtPanel from "../components/DoubtPanel";
import MessageList from "../components/MessageList";
import { useAuth } from "../context/AuthContext";
import { useAskSelection } from "../hooks/useAskSelection";

const SUGGESTIONS = [
  "Explain how recursion works with a simple example",
  "What's the difference between TCP and UDP?",
  "Help me understand how neural networks learn",
  "Summarize the causes of the French Revolution",
];

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export default function ChatPage({ conversationId, chats, toast, openSidebar }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const { sel, capture, clear } = useAskSelection();

  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [input, setInput] = useState("");
  const [openMsgId, setOpenMsgId] = useState(null);
  const [intent, setIntent] = useState(null);

  const abortRef = useRef(null);
  const skipLoadRef = useRef(null); // id of a chat we just created mid-stream: don't reload it
  const cidRef = useRef(conversationId);

  // ---- load whichever chat the URL points at ("/" is always a fresh, empty chat)
  useEffect(() => {
    cidRef.current = conversationId;
    if (conversationId !== null && skipLoadRef.current === conversationId) {
      skipLoadRef.current = null;
      return;
    }
    abortRef.current?.abort();
    setStreaming(false);
    setOpenMsgId(null);
    setIntent(null);
    setNotFound(false);
    if (conversationId === null) {
      setMessages([]);
      return;
    }
    let alive = true;
    setLoading(true);
    api
      .getConversation(conversationId)
      .then((rows) => alive && setMessages(rows))
      .catch((e) => {
        if (!alive) return;
        if (e.status === 404) setNotFound(true);
        else toast(e.message);
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [conversationId, toast]);

  // ---- arriving from search: scroll to the hit (and open the doubt thread if it was one)
  useEffect(() => {
    const m = params.get("m");
    if (!m || loading || messages.length === 0) return;
    const t = params.get("t");
    const el = document.getElementById(`msg-${m}`);
    el?.scrollIntoView({ block: "center" });
    el?.classList.add("flash");
    setTimeout(() => el?.classList.remove("flash"), 2000);
    if (t) {
      setOpenMsgId(Number(m));
      setIntent({ threadId: Number(t), nonce: Date.now() });
    }
    setParams({}, { replace: true });
  }, [params, loading, messages, setParams]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && setOpenMsgId(null);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  // ---- streaming
  const runStream = useCallback(
    async (path, body, { userText, regenerate = false }) => {
      const controller = new AbortController();
      abortRef.current = controller;
      const stamp = Date.now();
      const userTmp = `u-${stamp}`;
      const aId = `a-${stamp}`;
      let cid = cidRef.current;

      setStreaming(true);
      setMessages((m) => {
        const placeholder = { id: aId, role: "assistant", content: "", thread_count: 0 };
        return regenerate
          ? [...m.slice(0, -1), placeholder]
          : [...m, { id: userTmp, role: "user", content: userText }, placeholder];
      });

      const patchAssistant = (fn) => setMessages((m) => m.map((x) => (x.id === aId ? fn(x) : x)));

      try {
        await api.stream(
          path,
          body,
          (ev) => {
            if (ev.type === "conversation") {
              cid = ev.id;
              cidRef.current = ev.id;
              skipLoadRef.current = ev.id;
              chats.upsert({
                id: ev.id,
                title: userText.slice(0, 40),
                pinned: false,
                updated_at: new Date().toISOString(),
              });
              navigate(`/c/${ev.id}`, { replace: true });
            } else if (ev.type === "user") {
              setMessages((m) => m.map((x) => (x.id === userTmp ? { ...x, id: ev.id } : x)));
              if (cid) chats.upsert({ id: cid, updated_at: new Date().toISOString() });
            } else if (ev.type === "delta") {
              patchAssistant((x) => ({ ...x, content: x.content + ev.text }));
            } else if (ev.type === "done") {
              patchAssistant((x) => ({ ...x, id: ev.id }));
            } else if (ev.type === "title") {
              chats.patch(cid, { title: ev.title });
            } else if (ev.type === "error") {
              throw new Error(ev.message);
            }
          },
          controller.signal
        );
      } catch (e) {
        if (e.name !== "AbortError") {
          toast(e.message);
          setMessages((m) => m.filter((x) => x.id !== aId || x.content));
        }
      } finally {
        setStreaming(false);
        if (controller.signal.aborted && cid) {
          // Stopped by the user: the server keeps the partial reply. Sync real ids shortly after.
          setTimeout(async () => {
            try {
              const rows = await api.getConversation(cid);
              if (cidRef.current === cid) setMessages(rows);
            } catch {
              /* ignore */
            }
          }, 500);
        }
      }
    },
    [chats, navigate, toast]
  );

  const send = () => {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    runStream("/chat", { conversation_id: cidRef.current, message: text }, { userText: text });
  };

  const regenerate = () => {
    if (streaming || !cidRef.current) return;
    setOpenMsgId(null);
    runStream(`/conversations/${cidRef.current}/regenerate`, null, {
      userText: "",
      regenerate: true,
    });
  };

  const stop = () => abortRef.current?.abort();

  // ---- doubts
  const openDoubts = (id) => {
    setOpenMsgId(id);
    setIntent(null);
  };
  const onCount = useCallback(
    (mid, n) => setMessages((m) => m.map((x) => (x.id === mid ? { ...x, thread_count: n } : x))),
    []
  );
  const openMsg = messages.find((m) => m.id === openMsgId);

  const title = chats.chats.find((c) => c.id === conversationId)?.title;
  const isEmpty = conversationId === null && messages.length === 0;
  const name = user?.email?.split("@")[0];

  const composer = (
    <Composer
      value={input}
      onChange={setInput}
      onSend={send}
      onStop={stop}
      streaming={streaming}
      autoFocusKey={conversationId}
    />
  );

  return (
    <div className={"main" + (openMsg ? " with-panel" : "")}>
      <section className="chat" aria-label="Conversation">
        <header className="chat-head">
          <button className="icon-btn menu-btn" onClick={openSidebar} aria-label="Open sidebar">
            ☰
          </button>
          <h2 className="clip">{title || (isEmpty ? "New chat" : "")}</h2>
        </header>

        {notFound ? (
          <div className="center-state">
            <h2>Chat not found</h2>
            <p className="muted">It may have been deleted, or it belongs to another account.</p>
            <button className="btn primary" onClick={() => navigate("/")}>
              Start a new chat
            </button>
          </div>
        ) : isEmpty ? (
          <div className="hero">
            <h1>
              {greeting()}, {name}
            </h1>
            <p className="muted">
              Ask anything. Stuck on part of a reply? Highlight it and ask a doubt in a side window.
            </p>
            {composer}
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="suggest" onClick={() => setInput(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : loading ? (
          <div className="scroll">
            <div className="thread">
              {[90, 70, 85].map((w, i) => (
                <div key={i} className="skeleton line" style={{ width: `${w}%` }} />
              ))}
            </div>
          </div>
        ) : (
          <>
            <MessageList
              messages={messages}
              streaming={streaming}
              openMsgId={openMsgId}
              onRegenerate={regenerate}
              onOpenDoubts={openDoubts}
              onSelect={(m) => capture({ messageId: m.id })}
            />
            {composer}
          </>
        )}
      </section>

      {openMsg && (
        <DoubtPanel
          key={openMsg.id}
          message={openMsg}
          intent={intent}
          onClose={() => setOpenMsgId(null)}
          onCount={onCount}
        />
      )}
      <AskFab
        sel={sel}
        onAsk={(s) => {
          setOpenMsgId(s.messageId);
          setIntent({ quote: s.text, nonce: Date.now() });
          clear();
        }}
      />
    </div>
  );
}
