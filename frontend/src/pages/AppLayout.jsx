import { useCallback, useEffect, useState } from "react";
import { Navigate, useLocation, useMatch, useNavigate } from "react-router-dom";
import SearchDialog from "../components/SearchDialog";
import Sidebar from "../components/Sidebar";
import { useToast } from "../components/Modal";
import { useAuth } from "../context/AuthContext";
import { useConversations } from "../hooks/useConversations";
import ChatPage from "./ChatPage";

function useTheme() {
  const [theme, setTheme] = useState(() => {
    try {
      return (
        localStorage.getItem("dc_theme") ||
        (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light")
      );
    } catch {
      return "light";
    }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("dc_theme", theme);
    } catch {
      /* ignore */
    }
  }, [theme]);
  return [theme, setTheme];
}

/**
 * Persistent shell. ChatPage is rendered directly (not through a nested route) so it stays mounted
 * while the URL changes from "/" to "/c/:id": that is what lets a reply keep streaming while a new
 * chat gets its address.
 */
export default function AppLayout() {
  const { user, loading } = useAuth();
  const location = useLocation();
  const match = useMatch("/c/:id");

  if (loading) return <div className="splash">Loading…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (location.pathname !== "/" && !match) return <Navigate to="/" replace />;
  return <Shell activeId={match ? Number(match.params.id) : null} />;
}

/** Only mounted for signed-in users, so nothing is fetched before authentication. */
function Shell({ activeId }) {
  const navigate = useNavigate();
  const chats = useConversations();
  const [theme, setTheme] = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [toast, toastNode] = useToast();

  useEffect(() => {
    const onKey = (e) => {
      const mod = e.ctrlKey || e.metaKey;
      const key = e.key.toLowerCase();
      if (mod && key === "k") {
        e.preventDefault();
        setSearchOpen(true);
      } else if (mod && e.shiftKey && key === "o") {
        e.preventDefault();
        navigate("/");
      } else if (mod && key === "b") {
        e.preventDefault();
        setCollapsed((c) => !c);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [navigate]);

  const openSidebar = useCallback(() => {
    setCollapsed(false);
    setMobileOpen(true);
  }, []);

  return (
    <div className={"layout" + (collapsed ? " is-collapsed" : "")}>
      <Sidebar
        chats={chats}
        loading={chats.loading}
        activeId={activeId}
        open={mobileOpen}
        collapsed={collapsed}
        onClose={() => setMobileOpen(false)}
        onToggleCollapse={() => setCollapsed((c) => !c)}
        onSearch={() => {
          setMobileOpen(false);
          setSearchOpen(true);
        }}
        onError={toast}
        theme={theme}
        onTheme={setTheme}
      />
      <ChatPage conversationId={activeId} chats={chats} toast={toast} openSidebar={openSidebar} />
      {searchOpen && <SearchDialog chats={chats.chats} onClose={() => setSearchOpen(false)} />}
      {toastNode}
    </div>
  );
}
