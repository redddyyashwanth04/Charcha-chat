# DoubtChat

A ChatGPT / Claude-style chatbot with one idea those apps don't have: **a doubt window**.

When you're reading a reply and get stuck on a term, you don't have to derail the main conversation. Select the text, click **Ask doubt**, and a side window opens where you can ask as many questions as you like (even doubts about the doubt answers). Close it and you're exactly where you left off. Every doubt thread is saved and can be reopened later.

## Features

**Chat, like the big apps**
- Every visit starts on a **new empty chat** (`/`). A chat is only created when you send the first message, so empty chats never pile up.
- **Chat history** in the sidebar, grouped Pinned / Today / Yesterday / Previous 7 days / Previous 30 days / Older. Open any chat to continue it. Refresh keeps you on the same chat (`/c/:id`).
- **Auto-generated titles**, **rename**, **pin**, **delete** (with confirmation), **export to Markdown** (doubts included).
- **Search** (Ctrl/Cmd+K) across chats *and* doubts; selecting a doubt hit opens that exact thread.
- Streaming replies, **Stop** (keeps the partial reply), **Retry**, **Copy**, Markdown with code blocks and tables.
- Accounts (email + password), each user sees only their own chats.
- Light / dark theme, collapsible sidebar, mobile drawer, keyboard shortcuts.

**The doubt window**
- Highlight any passage, or use the **Doubts** button under a reply.
- Unlimited doubts per reply, each its own thread; **nested sub-doubts** up to 3 levels with a breadcrumb.
- Doubts **never leak into the main chat**: this is enforced and tested.

## Run it

You need Python 3.11+ and Node 18+.

```bash
./start.sh            # macOS / Linux: installs everything and starts both servers
```

Then open http://localhost:5173 and create an account.

Or manually:

```bash
# terminal 1: backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # Windows: copy .env.example .env
uvicorn app.main:app --reload --port 8000

# terminal 2: frontend
cd frontend
npm install
npm run dev
```

**Choose your AI** in `backend/.env`:

| `LLM_PROVIDER` | What you need |
|---|---|
| `gemini` (default) | free key from https://aistudio.google.com/apikey → `GEMINI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `ollama` | a local Ollama install, no key |
| `mock` (or `MOCK_LLM=1`) | nothing: fake streamed replies to try the UI |

Set `FALLBACK_PROVIDER` to automatically fail over to a second provider.

**Docker (Postgres + production build):** `cp backend/.env.example backend/.env`, edit it, then `docker compose up --build` and open http://localhost:8080.

## How the core promise works

| Request | What the model receives |
|---|---|
| Main chat message | The main conversation only (trimmed to a size budget). **Never** any doubt text. |
| A doubt | The original question + the one reply being questioned + that thread's own messages. |
| A nested doubt | The above + the chain of parent doubt threads it branched from. Never sibling threads. |

These rules are in `backend/app/services/` and verified by `backend/tests/test_context_isolation.py`.

## Architecture

```
backend/app/
  main.py            app factory, CORS, request logging
  config.py          settings from env (pydantic-settings)
  models.py          SQLAlchemy models: users, conversations, messages, doubt_threads, doubt_messages
  security.py        scrypt password hashing, JWT
  routers/           thin HTTP layer: auth, conversations, chat, doubts
  services/          business logic: chat_service, doubt_service, conversation_service
  llm/               one interface, providers: gemini, anthropic, openai/ollama, mock
                     + ResilientLLM (retry with backoff, fallback provider)
  prompts.py         all prompts in one place
frontend/src/
  pages/             AppLayout (shell), ChatPage, AuthPage
  components/        Sidebar, MessageList, Message, Composer, DoubtPanel, SearchDialog, Markdown…
  hooks/             useConversations, useDoubts, useAskSelection
  api.js             the only file that calls fetch (incl. NDJSON stream reader)
```

Replies stream as newline-delimited JSON events (`conversation`, `user`, `delta`, `done`, `title`, `error`).

## Tests and quality

```bash
cd backend && pip install -r requirements-dev.txt && pytest --cov=app && ruff check . && black --check .
cd frontend && npm test && npm run lint && npm run build
```

GitHub Actions (`.github/workflows/ci.yml`) runs all of it on every push.

## Known limits / next steps

- The login token is kept in `localStorage` (simple). For production, move it to an httpOnly cookie with refresh tokens.
- Database tables are created automatically at startup. Add Alembic migrations before changing the schema on real data.
- Rate limiting is in-memory (single server). Use Redis if you run several workers.
- Ideas: highlight passages that have doubts, a "doubt digest" that feeds resolved doubts back into the main chat (opt-in), token/cost tracking, file uploads.
