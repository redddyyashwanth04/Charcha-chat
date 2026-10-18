import { useCallback, useEffect, useState } from "react";
import * as api from "../api";

/** Sidebar chat history: loaded once, then kept in sync locally as the user chats. */
export function useConversations() {
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setChats(await api.listConversations());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh().catch(() => {});
  }, [refresh]);

  const upsert = useCallback((chat) => {
    setChats((list) => {
      const merged = { ...list.find((c) => c.id === chat.id), ...chat };
      const rest = list.filter((c) => c.id !== chat.id);
      const pinned = rest.filter((c) => c.pinned);
      const others = rest.filter((c) => !c.pinned);
      // pinned chats stay on top; the chat you just used goes to the top of the rest
      return merged.pinned ? [merged, ...pinned, ...others] : [...pinned, merged, ...others];
    });
  }, []);

  const patch = useCallback((id, fields) => {
    setChats((list) => list.map((c) => (c.id === id ? { ...c, ...fields } : c)));
  }, []);

  const remove = useCallback((id) => setChats((list) => list.filter((c) => c.id !== id)), []);

  return { chats, loading, refresh, upsert, patch, remove };
}
