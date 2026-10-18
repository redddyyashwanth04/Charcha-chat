"""The product's core promise: doubts and the main chat never contaminate each other."""

from tests.conftest import ask, reply_id, send


def _all_text(call) -> str:
    return call["system"] + "\n" + "\n".join(t for _, t in call["turns"])


def test_doubts_never_leak_into_main_chat_context(client, auth, llm):
    conv_id, _ = send(client, auth, "Explain recursion")
    mid = reply_id(client, auth, conv_id)
    llm.reply = "SECRET-DOUBT-ANSWER"
    ask(client, auth, mid, "SECRET-DOUBT-QUESTION?", quote="SECRET-QUOTE")
    ask(client, auth, mid, "SECRET-FOLLOWUP?")

    llm.calls.clear()
    llm.reply = "Next main answer."
    send(client, auth, "Now explain loops", conv_id)

    main_call = llm.stream_calls[0]
    text = _all_text(main_call)
    for secret in (
        "SECRET-DOUBT-ANSWER",
        "SECRET-DOUBT-QUESTION",
        "SECRET-QUOTE",
        "SECRET-FOLLOWUP",
    ):
        assert secret not in text
    # and the main history is just the real conversation
    assert [r for r, _ in main_call["turns"]] == ["user", "assistant", "user"]


def test_doubts_do_not_appear_in_main_message_list(client, auth, llm):
    conv_id, _ = send(client, auth, "hello")
    mid = reply_id(client, auth, conv_id)
    ask(client, auth, mid, "what?")
    msgs = client.get(f"/api/conversations/{conv_id}", headers=auth).json()
    assert len(msgs) == 2
    assert msgs[1]["thread_count"] == 1 and msgs[0]["thread_count"] == 0


def test_doubt_context_is_only_the_scoped_reply(client, auth, llm):
    llm.reply = "ANSWER-ONE"
    c1, _ = send(client, auth, "QUESTION-ONE")
    llm.reply = "ANSWER-TWO"
    send(client, auth, "QUESTION-TWO", c1)
    msgs = client.get(f"/api/conversations/{c1}", headers=auth).json()
    first_reply = [m for m in msgs if m["role"] == "assistant"][0]["id"]

    llm.calls.clear()
    llm.reply = "tutor says hi"
    ask(client, auth, first_reply, "what does this mean?", quote="a passage")
    call = llm.stream_calls[0]
    text = _all_text(call)
    assert "QUESTION-ONE" in text and "ANSWER-ONE" in text  # the scoped reply + its question
    assert "QUESTION-TWO" not in text and "ANSWER-TWO" not in text  # nothing else from the chat
    assert "a passage" in call["turns"][0][1] and "what does this mean?" in call["turns"][0][1]


def test_doubts_on_one_reply_never_reach_another_reply(client, auth, llm):
    c1, _ = send(client, auth, "first q")
    send(client, auth, "second q", c1)
    msgs = client.get(f"/api/conversations/{c1}", headers=auth).json()
    r1, r2 = [m["id"] for m in msgs if m["role"] == "assistant"]
    llm.reply = "REPLY-ONE-DOUBT-ANSWER"
    ask(client, auth, r1, "REPLY-ONE-DOUBT-QUESTION")

    llm.calls.clear()
    llm.reply = "reply two doubt answer"
    ask(client, auth, r2, "doubt on reply two")
    text = _all_text(llm.stream_calls[0])
    assert "REPLY-ONE-DOUBT" not in text


def test_followups_in_a_thread_keep_that_threads_history(client, auth, llm):
    conv_id, _ = send(client, auth, "hello")
    mid = reply_id(client, auth, conv_id)
    llm.reply = "FIRST-TUTOR-ANSWER"
    evs = ask(client, auth, mid, "first doubt")
    tid = next(e["id"] for e in evs if e["type"] == "thread")
    llm.calls.clear()
    ask(client, auth, mid, "second doubt", thread_id=tid)
    turns = llm.stream_calls[0]["turns"]
    assert [r for r, _ in turns] == ["user", "assistant", "user"]
    assert "FIRST-TUTOR-ANSWER" in turns[1][1]


def test_new_thread_does_not_include_sibling_thread(client, auth, llm):
    conv_id, _ = send(client, auth, "hello")
    mid = reply_id(client, auth, conv_id)
    llm.reply = "SIBLING-ANSWER"
    ask(client, auth, mid, "SIBLING-QUESTION")
    llm.calls.clear()
    ask(client, auth, mid, "a different doubt entirely")  # new thread, no thread_id
    assert "SIBLING" not in _all_text(llm.stream_calls[0])


def test_nested_doubt_includes_ancestor_chain_only(client, auth, llm):
    conv_id, _ = send(client, auth, "hello")
    mid = reply_id(client, auth, conv_id)
    llm.reply = "PARENT-TUTOR-ANSWER"
    parent_evs = ask(client, auth, mid, "PARENT-QUESTION", quote="PARENT-QUOTE")
    parent = next(e["id"] for e in parent_evs if e["type"] == "thread")
    llm.reply = "UNRELATED-ANSWER"
    ask(client, auth, mid, "UNRELATED-QUESTION")  # sibling root thread

    llm.calls.clear()
    llm.reply = "child answer"
    ask(client, auth, mid, "CHILD-QUESTION", parent_thread_id=parent, quote="inside parent answer")
    text = _all_text(llm.stream_calls[0])
    assert "PARENT-QUESTION" in text and "PARENT-TUTOR-ANSWER" in text and "PARENT-QUOTE" in text
    assert "UNRELATED" not in text
    threads = client.get(f"/api/messages/{mid}/threads", headers=auth).json()
    child = next(t for t in threads if t["parent_thread_id"] == parent)
    assert child["depth"] == 2


def test_nesting_depth_is_limited(client, auth, llm):
    conv_id, _ = send(client, auth, "hello")
    mid = reply_id(client, auth, conv_id)
    parent = None
    for _ in range(3):  # depth 1, 2, 3 are allowed
        evs = ask(client, auth, mid, "deeper", parent_thread_id=parent)
        parent = next(e["id"] for e in evs if e["type"] == "thread")
    r = client.post(
        f"/api/messages/{mid}/doubts",
        json={"question": "too deep", "parent_thread_id": parent},
        headers=auth,
    )
    assert r.status_code == 422


def test_cannot_use_thread_from_another_reply(client, auth, llm):
    conv_id, _ = send(client, auth, "q1")
    send(client, auth, "q2", conv_id)
    msgs = client.get(f"/api/conversations/{conv_id}", headers=auth).json()
    r1, r2 = [m["id"] for m in msgs if m["role"] == "assistant"]
    evs = ask(client, auth, r1, "doubt")
    tid = next(e["id"] for e in evs if e["type"] == "thread")
    r = client.post(
        f"/api/messages/{r2}/doubts", json={"question": "x", "thread_id": tid}, headers=auth
    )
    assert r.status_code == 404


def test_doubts_only_on_assistant_replies(client, auth):
    conv_id, _ = send(client, auth, "hello")
    msgs = client.get(f"/api/conversations/{conv_id}", headers=auth).json()
    user_msg = next(m["id"] for m in msgs if m["role"] == "user")
    r = client.post(f"/api/messages/{user_msg}/doubts", json={"question": "hi"}, headers=auth)
    assert r.status_code == 404


def test_delete_thread_removes_children(client, auth, llm):
    conv_id, _ = send(client, auth, "hello")
    mid = reply_id(client, auth, conv_id)
    evs = ask(client, auth, mid, "parent")
    parent = next(e["id"] for e in evs if e["type"] == "thread")
    ask(client, auth, mid, "child", parent_thread_id=parent)
    assert client.delete(f"/api/threads/{parent}", headers=auth).status_code == 204
    assert client.get(f"/api/messages/{mid}/threads", headers=auth).json() == []


def test_doubt_llm_failure_emits_error(client, auth, llm):
    conv_id, _ = send(client, auth, "hello")
    mid = reply_id(client, auth, conv_id)
    llm.fail = True
    evs = ask(client, auth, mid, "why?")
    assert evs[-1]["type"] == "error"
