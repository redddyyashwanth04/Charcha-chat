import json
import os
import tempfile
from collections.abc import Iterator

# Configure the app BEFORE importing it: temp DB, mock provider, relaxed limits.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256-ok"
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.llm import get_llm  # noqa: E402
from app.main import app  # noqa: E402
from app.ratelimit import limiter  # noqa: E402


class FakeLLM:
    """Records exactly what the model was sent, so tests can assert on context."""

    label = "fake:fake-1"

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.reply = "This is the assistant reply."
        self.fail = False

    def stream(self, system, turns, max_tokens=None) -> Iterator[str]:
        self.calls.append({"system": system, "turns": list(turns)})
        if self.fail:
            raise RuntimeError("boom")
        for word in self.reply.split(" "):
            yield word + " "

    def complete(self, system, turns, max_tokens=None) -> str:
        self.calls.append({"system": system, "turns": list(turns), "complete": True})
        return "Short Title"

    @property
    def stream_calls(self):
        return [c for c in self.calls if not c.get("complete")]


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    limiter.reset()
    yield


@pytest.fixture
def llm():
    fake = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_llm, None)


@pytest.fixture
def client(llm):
    with TestClient(app) as c:
        yield c


def register(client, email="a@example.com", password="password123"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return register(client)


def events(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def send(client, auth, text, conversation_id=None):
    r = client.post(
        "/api/chat", json={"conversation_id": conversation_id, "message": text}, headers=auth
    )
    assert r.status_code == 200, r.text
    evs = events(r)
    conv_id = next((e["id"] for e in evs if e["type"] == "conversation"), conversation_id)
    return conv_id, evs


def reply_id(client, auth, conv_id):
    msgs = client.get(f"/api/conversations/{conv_id}", headers=auth).json()
    return [m for m in msgs if m["role"] == "assistant"][-1]["id"]


def ask(client, auth, message_id, question, **extra):
    r = client.post(
        f"/api/messages/{message_id}/doubts",
        json={"question": question, **extra},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    return events(r)
