from app.config import Settings, get_settings
from app.errors import LLMError
from app.llm.base import LLMClient
from app.llm.resilient import ResilientLLM


def _build(provider: str, s: Settings) -> LLMClient:
    max_tokens = s.llm_max_output_tokens
    if provider == "mock":
        from app.llm.mock import MockLLM

        return MockLLM()
    if provider == "gemini":
        from app.llm.gemini import GeminiLLM

        return GeminiLLM(s.gemini_api_key, s.gemini_model, max_tokens)
    if provider == "anthropic":
        from app.llm.anthropic_client import AnthropicLLM

        return AnthropicLLM(s.anthropic_api_key, s.anthropic_model, max_tokens)
    if provider == "openai":
        from app.llm.openai_compat import OpenAICompatibleLLM

        return OpenAICompatibleLLM(
            "openai", s.openai_api_key, s.openai_model, s.openai_base_url, max_tokens
        )
    if provider == "ollama":
        from app.llm.openai_compat import OpenAICompatibleLLM

        return OpenAICompatibleLLM("ollama", None, s.ollama_model, s.ollama_base_url, max_tokens)
    raise LLMError(f"Unknown LLM provider: {provider}")


def get_llm() -> LLMClient:
    """FastAPI dependency. Tests override this with a FakeLLM."""
    s = get_settings()
    primary = _build(s.effective_provider, s)
    fallback = None
    if s.fallback_provider and s.fallback_provider != s.effective_provider:
        try:
            fallback = _build(s.fallback_provider, s)
        except LLMError:
            fallback = None  # misconfigured fallback must not break the primary path
    return ResilientLLM(primary, fallback, s.llm_retries)
