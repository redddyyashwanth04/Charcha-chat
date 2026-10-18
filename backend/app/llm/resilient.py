import logging
import time
from collections.abc import Iterator

from app.errors import LLMError
from app.llm.base import LLMClient, Turn

logger = logging.getLogger(__name__)


class ResilientLLM:
    """Retries with backoff, then falls back to a second provider.

    A retry or fallback only happens if NOTHING has been streamed to the user yet;
    once text is flowing we never switch models mid-answer.
    """

    def __init__(self, primary: LLMClient, fallback: LLMClient | None = None, retries: int = 2):
        self._clients = [c for c in (primary, fallback) if c is not None]
        self._retries = retries
        self.label = primary.label

    def stream(
        self, system: str, turns: list[Turn], max_tokens: int | None = None
    ) -> Iterator[str]:
        last_error: Exception | None = None
        for client in self._clients:
            for attempt in range(self._retries + 1):
                started = False
                try:
                    for piece in client.stream(system, turns, max_tokens):
                        started = True
                        yield piece
                    self.label = client.label
                    return
                except GeneratorExit:
                    raise
                except Exception as exc:  # provider SDKs raise many different types
                    last_error = exc
                    logger.warning(
                        "llm call failed",
                        extra={"extra_fields": {"provider": client.label, "attempt": attempt}},
                    )
                    if started:
                        raise LLMError("The response was interrupted. Please try again.") from exc
                    time.sleep(min(0.5 * 2**attempt, 4))
        raise LLMError(_friendly(last_error)) from last_error

    def complete(self, system: str, turns: list[Turn], max_tokens: int | None = None) -> str:
        return "".join(self.stream(system, turns, max_tokens)).strip()


def _friendly(exc: Exception | None) -> str:
    if isinstance(exc, LLMError):
        return exc.message
    return "The AI provider is unavailable right now. Please try again in a moment."
