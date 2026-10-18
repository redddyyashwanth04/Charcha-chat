from collections.abc import Iterator

from app.errors import LLMError
from app.llm.base import Turn


class AnthropicLLM:
    def __init__(self, api_key: str | None, model: str, default_max_tokens: int = 4096):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set. Add it to backend/.env")
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max = default_max_tokens
        self.label = f"anthropic:{model}"

    def stream(
        self, system: str, turns: list[Turn], max_tokens: int | None = None
    ) -> Iterator[str]:
        messages = [{"role": role, "content": text} for role, text in turns]
        with self._client.messages.stream(
            model=self._model,
            max_tokens=max_tokens or self._max,
            system=system,
            messages=messages,
        ) as stream:
            yield from stream.text_stream

    def complete(self, system: str, turns: list[Turn], max_tokens: int | None = None) -> str:
        return "".join(self.stream(system, turns, max_tokens)).strip()
