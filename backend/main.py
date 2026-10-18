"""DoubtChat backend.

Key idea: the main conversation and the "doubt" side-threads are stored and
prompted separately. A doubt thread is attached to ONE assistant message, and
the model only sees that message (plus the question that produced it) as
context, never the whole chat. Doubts never pollute the main conversation.
"""
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "doubtchat.db")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
API_KEY = os.getenv("GEMINI_API_KEY")
MOCK = os.getenv("MOCK_LLM") == "1"  # offline dev/testing without an API key

MAIN_SYSTEM = (
    "You are a clear, friendly assistant. Answer in well-structured Markdown, "
    "stay focused on what was asked, and avoid padding. The user can ask side "
    "questions about any part of your answer in a separate doubt window, so "
    "you don't need to pre-explain every possible term."
)

DOUBT_SYSTEM = """You are a doubt-clearing tutor in a side window of a chat app.

The user is in the middle of reading an answer and got stuck on something.
Your only job: clear that specific doubt so they can go back to reading.

Rules:
- Answer ONLY the doubt asked. Do not continue or extend the original topic.
- Be concise and use simple language. Add a short example or analogy if it helps.
- If the user quotes a passage, the doubt is about that passage.
- Do not repeat the whole original answer back.
- Do not suggest new topics or end with follow-up questions. When the doubt is clear, stop.

--- Original question the user asked ---
{question}

--- The answer the user is reading (this is your only context) ---
{answer}
"""

app = FastAPI(title="DoubtChat")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- database ----------
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS doubts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                quote TEXT,
                created_at REAL NOT NULL
            );
            """
        )


init_db()


# ---------- LLM layer ----------
def stream_llm(system: str, turns: list[tuple[str, str]]):
    """Yield text chunks. `turns` is a list of (role, text), role in {'user','model'}."""
    if MOCK:
        last = turns[-1][1]
        reply = f"(mock reply) You said: {last[:200]}. " + "This is streamed token by token. " * 4
        for word in reply.split(" "):
            time.sleep(0.02)
            yield word + " "
        return

    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to backend/.env")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=API_KEY)
    contents = [
        types.Content(role=role, parts=[types.Part(text=text)]) for role, text in turns
    ]
    stream = client.models.generate_content_stream(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system),
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text


def event(obj: dict) -> str:
    return json.dumps(obj) + "\n"  # NDJSON: one JSON event per line


def with_quote(question: str, quote: Optional[str]) -> str:
    if quote:
        return f'(Regarding this passage: "{quote}")\n\n{question}'
    return question


# ---------- schemas ----------
class ChatIn(BaseModel):
    message: str


class DoubtIn(BaseModel):
    question: str
    quote: Optional[str] = None


# ---------- conversations ----------
@app.get("/api/conversations")
def list_conversations():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at FROM conversations ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/conversations")
def create_conversation():
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (title, created_at) VALUES (?, ?)",
            ("New chat", time.time()),
        )
        return {"id": cur.lastrowid, "title": "New chat"}


@app.delete("/api/conversations/{cid}")
def delete_conversation(cid: int):
    with get_db() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))
    return {"ok": True}


@app.get("/api/conversations/{cid}")
def get_conversation(cid: int):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.role, m.content,
                   (SELECT COUNT(*) FROM doubts d
                     WHERE d.message_id = m.id AND d.role = 'user') AS doubt_count
            FROM messages m WHERE m.conversation_id = ? ORDER BY m.id
            """,
            (cid,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------- main chat (streaming) ----------
@app.post("/api/conversations/{cid}/chat")
def chat(cid: int, body: ChatIn):
    text = body.message.strip()
    if not text:
        raise HTTPException(400, "Empty message")

    with get_db() as conn:
        conv = conn.execute("SELECT * FROM conversations WHERE id = ?", (cid,)).fetchone()
        if not conv:
            raise HTTPException(404, "Conversation not found")
        cur = conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?,?,?,?)",
            (cid, "user", text, time.time()),
        )
        user_id = cur.lastrowid
        if conv["title"] == "New chat":
            conn.execute(
                "UPDATE conversations SET title = ? WHERE id = ?", (text[:50], cid)
            )
        history = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id",
            (cid,),
        ).fetchall()

    # Main chat context = main messages only. Doubts are deliberately excluded.
    turns = [("user" if r["role"] == "user" else "model", r["content"]) for r in history]

    def gen():
        yield event({"type": "user", "id": user_id})
        parts: list[str] = []
        try:
            for piece in stream_llm(MAIN_SYSTEM, turns):
                parts.append(piece)
                yield event({"type": "delta", "text": piece})
        except Exception as e:  # surface API errors to the UI
            yield event({"type": "error", "message": str(e)})
            return
        full = "".join(parts).strip()
        if not full:
            yield event({"type": "error", "message": "Model returned an empty response."})
            return
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?,?,?,?)",
                (cid, "assistant", full, time.time()),
            )
            aid = cur.lastrowid
        yield event({"type": "done", "id": aid})

    return StreamingResponse(gen(), media_type="application/x-ndjson")


# ---------- doubts (streaming, scoped to one assistant message) ----------
@app.get("/api/messages/{mid}/doubts")
def get_doubts(mid: int):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, role, content, quote FROM doubts WHERE message_id = ? ORDER BY id",
            (mid,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/messages/{mid}/doubts")
def ask_doubt(mid: int, body: DoubtIn):
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Empty question")

    with get_db() as conn:
        parent = conn.execute("SELECT * FROM messages WHERE id = ?", (mid,)).fetchone()
        if not parent or parent["role"] != "assistant":
            raise HTTPException(404, "Assistant message not found")
        original_q = conn.execute(
            """SELECT content FROM messages
               WHERE conversation_id = ? AND role = 'user' AND id < ?
               ORDER BY id DESC LIMIT 1""",
            (parent["conversation_id"], mid),
        ).fetchone()
        prior = conn.execute(
            "SELECT role, content, quote FROM doubts WHERE message_id = ? ORDER BY id",
            (mid,),
        ).fetchall()
        conn.execute(
            "INSERT INTO doubts (message_id, role, content, quote, created_at) VALUES (?,?,?,?,?)",
            (mid, "user", question, body.quote, time.time()),
        )

    system = DOUBT_SYSTEM.format(
        question=original_q["content"] if original_q else "(not available)",
        answer=parent["content"],
    )
    # Context = parent answer (in system prompt) + this doubt thread only.
    turns = [
        (
            "user" if r["role"] == "user" else "model",
            with_quote(r["content"], r["quote"]) if r["role"] == "user" else r["content"],
        )
        for r in prior
    ]
    turns.append(("user", with_quote(question, body.quote)))

    def gen():
        parts: list[str] = []
        try:
            for piece in stream_llm(system, turns):
                parts.append(piece)
                yield event({"type": "delta", "text": piece})
        except Exception as e:
            yield event({"type": "error", "message": str(e)})
            return
        full = "".join(parts).strip()
        if full:
            with get_db() as conn:
                cur = conn.execute(
                    "INSERT INTO doubts (message_id, role, content, quote, created_at) VALUES (?,?,?,?,?)",
                    (mid, "assistant", full, None, time.time()),
                )
                did = cur.lastrowid
            yield event({"type": "done", "id": did})

    return StreamingResponse(gen(), media_type="application/x-ndjson")
