from collections.abc import Iterator

from app.errors import LLMError
from app.llm.base import Turn


class GeminiLLM:
    def __init__(self, api_key: str | None, model: str, default_max_tokens: int = 4096):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set. Add it to backend/.env")
        import httpx
        from google import genai
        from google.genai import types as _types

        # Some environments have corporate/custom SSL certificates that Python's
        # default SSL context does not trust. We pass a custom httpx client with
        # SSL verification disabled so outbound requests to Gemini still work.
        _http_client = httpx.Client(verify=False)
        _http_options = _types.HttpOptions(httpx_client=_http_client)
        self._client = genai.Client(api_key=api_key, http_options=_http_options)
        self._model = model
        self._max = default_max_tokens
        self.label = f"gemini:{model}"

    def stream(
        self, system: str, turns: list[Turn], max_tokens: int | None = None
    ) -> Iterator[str]:
        from google.genai import types

        contents = [
            types.Content(
                role="model" if role == "assistant" else "user", parts=[types.Part(text=t)]
            )
            for role, t in turns
        ]
        cfg = types.GenerateContentConfig(
            system_instruction=system, max_output_tokens=max_tokens or self._max
        )
        for chunk in self._client.models.generate_content_stream(
            model=self._model, contents=contents, config=cfg
        ):
            if chunk.text:
                yield chunk.text

    def complete(self, system: str, turns: list[Turn], max_tokens: int | None = None) -> str:
        return "".join(self.stream(system, turns, max_tokens)).strip()
