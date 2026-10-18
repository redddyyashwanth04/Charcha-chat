import time
from collections.abc import Iterator

from app.llm.base import Turn


class MockLLM:
    """Offline provider for development and demos. Streams a canned Markdown answer."""

    label = "mock:mock-1"

    def stream(
        self, system: str, turns: list[Turn], max_tokens: int | None = None
    ) -> Iterator[str]:
        last = turns[-1][1] if turns else ""
        if "title" in system.lower() and "doubt-clearing" not in system:
            yield "Mock chat title"
            return
        if "doubt-clearing tutor" in system:
            text = (
                f"Here's a quick clarification. You asked: *{last[:120]}*\n\n"
                "In short, this part means the idea is applied step by step. "
                "For example, think of it like following a recipe."
            )
        else:
            text = (
                f"## About: {last[:60]}\n\n"
                "This is a **mock reply** streamed token by token, so you can try the UI "
                "without an API key.\n\n"
                "- Select any text here and click *Ask doubt* to open the doubt window.\n"
                "- Your main chat stays exactly where you left it.\n\n"
                "```python\nprint('hello from DoubtChat')\n```\n"
            )
        for word in text.split(" "):
            time.sleep(0.01)
            yield word + " "

    def complete(self, system: str, turns: list[Turn], max_tokens: int | None = None) -> str:
        if "title" in system.lower():
            return "Mock chat title"
        return "".join(self.stream(system, turns, max_tokens)).strip()
