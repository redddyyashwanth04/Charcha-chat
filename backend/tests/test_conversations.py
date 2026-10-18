from tests.conftest import events, register, reply_id, send


def test_new_chat_is_created_lazily_on_first_message(client, auth):
    assert client.get("/api/conversations", headers=auth).json() == []
    conv_id, evs = send(client, auth, "Explain recursion")
    assert evs[0]["type"] == "conversation"  # first event lets the UI navigate immediately
    types = [e["type"] for e in evs]
    assert "delta" in types and "done" in types and "title" in types
    convs = client.get("/api/conversations", headers=auth).json()
    assert len(convs) == 1 and convs[0]["id"] == conv_id


def test_auto_title_is_generated_and_saved(client, auth):
    conv_id, evs = send(client, auth, "Explain recursion")
    assert next(e for e in evs if e["type"] == "title")["title"] == "Short Title"
    assert client.get("/api/conversations", headers=auth).json()[0]["title"] == "Short Title"


def test_messages_are_persisted_in_order(client, auth):
    conv_id, _ = send(client, auth, "Hi")
    send(client, auth, "And again", conv_id)
    msgs = client.get(f"/api/conversations/{conv_id}", headers=auth).json()
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[1]["content"].strip() == "This is the assistant reply."


def test_history_ordered_by_recent_activity_with_pinned_first(client, auth):
    a, _ = send(client, auth, "first chat")
    b, _ = send(client, auth, "second chat")
    order = [c["id"] for c in client.get("/api/conversations", headers=auth).json()]
    assert order == [b, a]
    send(client, auth, "bump the first", a)  # most recent activity moves it to the top
    order = [c["id"] for c in client.get("/api/conversations", headers=auth).json()]
    assert order == [a, b]
    client.patch(f"/api/conversations/{b}/pin", json={"pinned": True}, headers=auth)
    order = [c["id"] for c in client.get("/api/conversations", headers=auth).json()]
    assert order == [b, a]


def test_rename(client, auth):
    conv_id, _ = send(client, auth, "hello")
    r = client.patch(f"/api/conversations/{conv_id}", json={"title": "  My topic "}, headers=auth)
    assert r.json()["title"] == "My topic"
    assert (
        client.patch(f"/api/conversations/{conv_id}", json={"title": ""}, headers=auth).status_code
        == 422
    )


def test_title_search_filter(client, auth, llm):
    a, _ = send(client, auth, "alpha")
    client.patch(f"/api/conversations/{a}", json={"title": "Python tips"}, headers=auth)
    b, _ = send(client, auth, "beta")
    client.patch(f"/api/conversations/{b}", json={"title": "Cooking"}, headers=auth)
    found = client.get("/api/conversations?q=python", headers=auth).json()
    assert [c["id"] for c in found] == [a]


def test_delete_cascades_messages_and_doubts(client, auth):
    from app.db import SessionLocal
    from app.models import DoubtMessage, DoubtThread, Message

    conv_id, _ = send(client, auth, "hello")
    mid = reply_id(client, auth, conv_id)
    client.post(f"/api/messages/{mid}/doubts", json={"question": "why?"}, headers=auth)
    assert client.delete(f"/api/conversations/{conv_id}", headers=auth).status_code == 204
    with SessionLocal() as db:
        assert db.query(Message).count() == 0
        assert db.query(DoubtThread).count() == 0
        assert db.query(DoubtMessage).count() == 0
    assert client.get(f"/api/conversations/{conv_id}", headers=auth).status_code == 404


def test_unknown_conversation_is_404(client, auth):
    assert client.get("/api/conversations/999", headers=auth).status_code == 404
    r = client.post("/api/chat", json={"conversation_id": 999, "message": "hi"}, headers=auth)
    assert r.status_code == 404


def test_empty_message_rejected(client, auth):
    r = client.post("/api/chat", json={"conversation_id": None, "message": ""}, headers=auth)
    assert r.status_code == 422
    r = client.post("/api/chat", json={"conversation_id": None, "message": "   "}, headers=auth)
    assert r.status_code == 422
    assert client.get("/api/conversations", headers=auth).json() == []  # nothing was created


def test_llm_failure_emits_error_event_and_saves_no_assistant_message(client, auth, llm):
    llm.fail = True
    conv_id, evs = send(client, auth, "hello")
    assert evs[-1]["type"] == "error"
    msgs = client.get(f"/api/conversations/{conv_id}", headers=auth).json()
    assert [m["role"] for m in msgs] == ["user"]


def test_regenerate_replaces_last_reply(client, auth, llm):
    conv_id, _ = send(client, auth, "hello")
    old = reply_id(client, auth, conv_id)
    llm.reply = "A brand new answer."
    r = client.post(f"/api/conversations/{conv_id}/regenerate", headers=auth)
    assert any(e["type"] == "done" for e in events(r))
    msgs = client.get(f"/api/conversations/{conv_id}", headers=auth).json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["id"] != old and "brand new" in msgs[1]["content"]


def test_regenerate_without_reply_is_rejected(client, auth, llm):
    llm.fail = True
    conv_id, _ = send(client, auth, "hello")
    assert client.post(f"/api/conversations/{conv_id}/regenerate", headers=auth).status_code == 422


def test_export_markdown_includes_doubts(client, auth):
    conv_id, _ = send(client, auth, "hello")
    mid = reply_id(client, auth, conv_id)
    client.post(
        f"/api/messages/{mid}/doubts",
        json={"question": "what is X?", "quote": "reply"},
        headers=auth,
    )
    r = client.get(f"/api/conversations/{conv_id}/export", headers=auth)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert "what is X?" in r.text and "<details>" in r.text
    r2 = client.get(f"/api/conversations/{conv_id}/export?include_doubts=false", headers=auth)
    assert "what is X?" not in r2.text


def test_search_finds_messages_and_doubts(client, auth, llm):
    llm.reply = "Photosynthesis happens in chloroplasts."
    conv_id, _ = send(client, auth, "tell me about plants")
    mid = reply_id(client, auth, conv_id)
    llm.reply = "Stroma is the fluid inside."
    client.post(f"/api/messages/{mid}/doubts", json={"question": "what is stroma?"}, headers=auth)
    hits = client.get("/api/search?q=chloroplast", headers=auth).json()
    assert hits and hits[0]["kind"] == "message"
    dh = client.get("/api/search?q=stroma", headers=auth).json()
    assert {h["kind"] for h in dh} == {"doubt"} and dh[0]["thread_id"]
    assert client.get("/api/search?q=zzzz", headers=auth).json() == []


def test_users_cannot_touch_each_others_data(client, auth):
    other = register(client, "b@example.com")
    conv_id, _ = send(client, auth, "my private chat")
    mid = reply_id(client, auth, conv_id)
    assert client.get("/api/conversations", headers=other).json() == []
    assert client.get(f"/api/conversations/{conv_id}", headers=other).status_code == 404
    assert (
        client.patch(
            f"/api/conversations/{conv_id}", json={"title": "x"}, headers=other
        ).status_code
        == 404
    )
    assert client.delete(f"/api/conversations/{conv_id}", headers=other).status_code == 404
    assert client.get(f"/api/conversations/{conv_id}/export", headers=other).status_code == 404
    r = client.post("/api/chat", json={"conversation_id": conv_id, "message": "hi"}, headers=other)
    assert r.status_code == 404
    r = client.post(f"/api/messages/{mid}/doubts", json={"question": "hey"}, headers=other)
    assert r.status_code == 404
    assert client.get(f"/api/messages/{mid}/threads", headers=other).status_code == 404
    assert client.get("/api/search?q=private", headers=other).json() == []
