from collections.abc import Iterator
from typing import Protocol

Turn = tuple[str, str]  # (role, text) with role in {"user", "assistant"}


class LLMClient(Protocol):
    """Every provider implements this. Routes and services only ever see this interface."""

    label: str  # e.g. "gemini:gemini-2.5-flash"

    def stream(
        self, system: str, turns: list[Turn], max_tokens: int | None = None
    ) -> Iterator[str]: ...

    def complete(self, system: str, turns: list[Turn], max_tokens: int | None = None) -> str: ...
