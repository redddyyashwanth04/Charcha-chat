import pytest

from app.errors import LLMError
from app.llm.resilient import ResilientLLM
from app.services.chat_service import trim_history


def test_trim_keeps_everything_when_under_budget():
    turns = [("user", "a"), ("assistant", "b"), ("user", "c")]
    assert trim_history(turns, 1000) == turns


def test_trim_drops_oldest_and_never_starts_on_assistant():
    turns = [
        ("user", "x" * 50),
        ("assistant", "y" * 50),
        ("user", "z" * 50),
        ("assistant", "w" * 50),
        ("user", "last"),
    ]
    out = trim_history(turns, 120)
    assert out[0][0] == "user"
    assert out[-1] == ("user", "last")
    assert len(out) < len(turns)


def test_trim_always_keeps_latest_turn_even_if_over_budget():
    assert trim_history([("user", "x" * 500)], 10) == [("user", "x" * 500)]


class Flaky:
    def __init__(self, fail_times, label="flaky:x", partial=False):
        self.fail_times, self.calls, self.label, self.partial = fail_times, 0, label, partial

    def stream(self, system, turns, max_tokens=None):
        self.calls += 1
        if self.partial:
            yield "start "
            raise RuntimeError("dropped")
        if self.calls <= self.fail_times:
            raise RuntimeError("503")
        yield "ok"

    def complete(self, *a, **k):
        return "".join(self.stream(*a, **k))


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("app.llm.resilient.time.sleep", lambda s: None)


def test_retries_then_succeeds():
    llm = Flaky(fail_times=2)
    assert "".join(ResilientLLM(llm, retries=2).stream("s", [("user", "hi")])) == "ok"
    assert llm.calls == 3


def test_falls_back_to_second_provider():
    primary, fallback = Flaky(fail_times=99), Flaky(fail_times=0, label="fb:y")
    llm = ResilientLLM(primary, fallback, retries=1)
    assert "".join(llm.stream("s", [("user", "hi")])) == "ok"
    assert llm.label == "fb:y"


def test_raises_friendly_error_when_everything_fails():
    with pytest.raises(LLMError):
        list(ResilientLLM(Flaky(fail_times=99), retries=1).stream("s", [("user", "hi")]))


def test_never_retries_after_text_was_streamed():
    llm = Flaky(fail_times=0, partial=True)
    out = []
    with pytest.raises(LLMError):
        for piece in ResilientLLM(llm, Flaky(0), retries=2).stream("s", [("user", "hi")]):
            out.append(piece)
    assert out == ["start "] and llm.calls == 1
