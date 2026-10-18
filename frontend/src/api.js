const BASE = "/api";
const TOKEN_KEY = "dc_token";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

let token = null;
try {
  token = localStorage.getItem(TOKEN_KEY);
} catch {
  /* storage unavailable: session will not persist */
}

let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn;
};

export function setToken(value) {
  token = value;
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}
export const hasToken = () => Boolean(token);

const authHeader = () => (token ? { Authorization: `Bearer ${token}` } : {});

async function toError(res) {
  let message = `Request failed (${res.status})`;
  try {
    const data = await res.json();
    message = data?.error?.message || data?.detail || message;
  } catch {
    /* non-JSON error body */
  }
  if (res.status === 401 && token) onUnauthorized();
  return new ApiError(message, res.status);
}

async function request(path, { method = "GET", body } = {}) {
  const res = await fetch(BASE + path, {
    method,
    headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...authHeader() },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await toError(res);
  return res.status === 204 ? null : res.json();
}

// ---- auth
export const register = (email, password) =>
  request("/auth/register", { method: "POST", body: { email, password } });
export const login = (email, password) =>
  request("/auth/login", { method: "POST", body: { email, password } });
export const me = () => request("/auth/me");

// ---- conversations
export const listConversations = () => request("/conversations");
export const getConversation = (id) => request(`/conversations/${id}`);
export const renameConversation = (id, title) =>
  request(`/conversations/${id}`, { method: "PATCH", body: { title } });
export const pinConversation = (id, pinned) =>
  request(`/conversations/${id}/pin`, { method: "PATCH", body: { pinned } });
export const deleteConversation = (id) => request(`/conversations/${id}`, { method: "DELETE" });
export const search = (q) => request(`/search?q=${encodeURIComponent(q)}`);

export async function exportConversation(id, title) {
  const res = await fetch(`${BASE}/conversations/${id}/export?include_doubts=true`, {
    headers: authHeader(),
  });
  if (!res.ok) throw await toError(res);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `${title || "chat"}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---- doubts
export const getThreads = (messageId) => request(`/messages/${messageId}/threads`);
export const deleteThread = (threadId) => request(`/threads/${threadId}`, { method: "DELETE" });

// ---- streaming (NDJSON: one JSON event per line)
export function createLineParser(onEvent) {
  let buffer = "";
  return (chunk) => {
    buffer += chunk;
    let nl;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (line) onEvent(JSON.parse(line));
    }
  };
}

export async function stream(path, body, onEvent, signal) {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });
  if (!res.ok || !res.body) throw await toError(res);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const push = createLineParser(onEvent);
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    push(decoder.decode(value, { stream: true }));
  }
}
