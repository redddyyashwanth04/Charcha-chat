import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../api";
import { useAuth } from "../context/AuthContext";
import { groupByDate } from "../lib/groupByDate";
import { ConfirmDialog } from "./Modal";

function Row({ chat, active, onOpen, onChanged, onRemoved, onError }) {
  const [menu, setMenu] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [title, setTitle] = useState(chat.title);
  const [confirm, setConfirm] = useState(false);
  const rowRef = useRef(null);

  useEffect(() => {
    if (!menu) return;
    const off = (e) => !rowRef.current?.contains(e.target) && setMenu(false);
    document.addEventListener("mousedown", off);
    return () => document.removeEventListener("mousedown", off);
  }, [menu]);

  const commitRename = async () => {
    setRenaming(false);
    const next = title.trim();
    if (!next || next === chat.title) return setTitle(chat.title);
    try {
      onChanged(await api.renameConversation(chat.id, next));
    } catch (e) {
      setTitle(chat.title);
      onError(e.message);
    }
  };

  const act = (fn) => async () => {
    setMenu(false);
    try {
      await fn();
    } catch (e) {
      onError(e.message);
    }
  };

  return (
    <li ref={rowRef} className={"chat-row" + (active ? " active" : "")}>
      {renaming ? (
        <input
          className="rename"
          autoFocus
          value={title}
          maxLength={120}
          aria-label="Chat title"
          onChange={(e) => setTitle(e.target.value)}
          onBlur={commitRename}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitRename();
            if (e.key === "Escape") {
              setTitle(chat.title);
              setRenaming(false);
            }
          }}
        />
      ) : (
        <button className="chat-link" onClick={() => onOpen(chat.id)} title={chat.title}>
          {chat.pinned && <span aria-label="Pinned">📌 </span>}
          {chat.title}
        </button>
      )}
      {!renaming && (
        <button
          className="dots"
          aria-label={`Options for ${chat.title}`}
          aria-haspopup="menu"
          onClick={() => setMenu((m) => !m)}
        >
          ⋯
        </button>
      )}
      {menu && (
        <div className="menu" role="menu">
          <button
            role="menuitem"
            onClick={act(async () => onChanged(await api.pinConversation(chat.id, !chat.pinned)))}
          >
            {chat.pinned ? "Unpin" : "Pin"}
          </button>
          <button
            role="menuitem"
            onClick={() => {
              setMenu(false);
              setRenaming(true);
            }}
          >
            Rename
          </button>
          <button role="menuitem" onClick={act(() => api.exportConversation(chat.id, chat.title))}>
            Export as Markdown
          </button>
          <button
            role="menuitem"
            className="danger-text"
            onClick={() => {
              setMenu(false);
              setConfirm(true);
            }}
          >
            Delete
          </button>
        </div>
      )}
      {confirm && (
        <ConfirmDialog
          title="Delete this chat?"
          body={`“${chat.title}” and all of its doubts will be permanently deleted.`}
          onCancel={() => setConfirm(false)}
          onConfirm={async () => {
            setConfirm(false);
            try {
              await api.deleteConversation(chat.id);
              onRemoved(chat.id);
            } catch (e) {
              onError(e.message);
            }
          }}
        />
      )}
    </li>
  );
}

export default function Sidebar({
  chats,
  loading,
  activeId,
  open,
  collapsed,
  onClose,
  onToggleCollapse,
  onSearch,
  onError,
  theme,
  onTheme,
}) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [userMenu, setUserMenu] = useState(false);
  const groups = useMemo(() => groupByDate(chats.chats), [chats.chats]);

  const go = (path) => {
    navigate(path);
    onClose();
  };

  return (
    <>
      {open && <div className="scrim" onClick={onClose} />}
      <aside
        className={"sidebar" + (open ? " open" : "") + (collapsed ? " collapsed" : "")}
        aria-label="Chat history"
      >
        <div className="side-top">
          <div className="brand">
            <span className="logo">D</span>
            <span>DoubtChat</span>
          </div>
          <button
            className="icon-btn hide-mobile"
            onClick={onToggleCollapse}
            aria-label="Collapse sidebar"
            title="Collapse sidebar (Ctrl+B)"
          >
            ◧
          </button>
        </div>

        <button className="new-chat" onClick={() => go("/")} title="New chat (Ctrl+Shift+O)">
          <span>＋</span> New chat
        </button>
        <button className="side-search" onClick={onSearch} title="Search (Ctrl+K)">
          <span>⌕</span> Search chats
        </button>

        <nav className="history">
          {loading && (
            <div className="skeletons" aria-label="Loading chats">
              {[70, 55, 80, 60, 75].map((w, i) => (
                <div key={i} className="skeleton" style={{ width: `${w}%` }} />
              ))}
            </div>
          )}
          {!loading && groups.length === 0 && (
            <p className="muted small pad">No chats yet. Start one and it will show up here.</p>
          )}
          {groups.map((g) => (
            <section key={g.label}>
              <h4>{g.label}</h4>
              <ul>
                {g.items.map((c) => (
                  <Row
                    key={c.id}
                    chat={c}
                    active={c.id === activeId}
                    onOpen={(id) => go(`/c/${id}`)}
                    onChanged={(updated) => chats.patch(updated.id, updated)}
                    onRemoved={(id) => {
                      chats.remove(id);
                      if (id === activeId) navigate("/", { replace: true });
                    }}
                    onError={onError}
                  />
                ))}
              </ul>
            </section>
          ))}
        </nav>

        <div className="side-foot">
          <button className="user" onClick={() => setUserMenu((m) => !m)} aria-haspopup="menu">
            <span className="avatar">{user?.email?.[0]?.toUpperCase()}</span>
            <span className="clip">{user?.email}</span>
          </button>
          {userMenu && (
            <div className="menu up" role="menu">
              <button role="menuitem" onClick={() => onTheme(theme === "dark" ? "light" : "dark")}>
                {theme === "dark" ? "Light mode" : "Dark mode"}
              </button>
              <button role="menuitem" onClick={logout}>
                Log out
              </button>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
