from collections.abc import Iterator

from app.errors import LLMError
from app.llm.base import Turn


class OpenAICompatibleLLM:
    """Works for OpenAI and for Ollama (which exposes an OpenAI-compatible endpoint)."""

    def __init__(
        self,
        provider: str,
        api_key: str | None,
        model: str,
        base_url: str | None = None,
        default_max_tokens: int = 4096,
    ):
        if provider == "openai" and not api_key:
            raise LLMError("OPENAI_API_KEY is not set. Add it to backend/.env")
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key or "ollama", base_url=base_url)
        self._model = model
        self._max = default_max_tokens
        self.label = f"{provider}:{model}"

    def stream(
        self, system: str, turns: list[Turn], max_tokens: int | None = None
    ) -> Iterator[str]:
        messages = [{"role": "system", "content": system}] + [
            {"role": role, "content": text} for role, text in turns
        ]
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens or self._max,
            stream=True,
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def complete(self, system: str, turns: list[Turn], max_tokens: int | None = None) -> str:
        return "".join(self.stream(system, turns, max_tokens)).strip()
