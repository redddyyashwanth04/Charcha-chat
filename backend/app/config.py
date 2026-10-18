from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "dev-secret-change-me"


class Settings(BaseSettings):
    """All configuration comes from environment variables / backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"  # dev | prod
    log_level: str = "INFO"
    database_url: str = "sqlite:///./doubtchat.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # auth
    jwt_secret: str = DEFAULT_SECRET
    access_token_days: int = 7

    # llm
    llm_provider: str = "gemini"  # gemini | anthropic | openai | ollama | mock
    fallback_provider: str | None = None
    mock_llm: bool = False  # shortcut for llm_provider=mock
    llm_retries: int = 2
    llm_max_output_tokens: int = 4096

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1"

    # behaviour
    rate_limit_per_minute: int = 30
    context_char_budget: int = 60000
    max_doubt_depth: int = 3

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_provider(self) -> str:
        return "mock" if self.mock_llm else self.llm_provider

    @model_validator(mode="after")
    def _require_real_secret_in_prod(self):
        if self.app_env == "prod" and self.jwt_secret == DEFAULT_SECRET:
            raise ValueError("JWT_SECRET must be set when APP_ENV=prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
