from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_JWT_SECRET = "dev-secret-change-me"
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_ROOT / ".env", extra="ignore")

    app_env: str = "development"  # development | production

    database_url: str = "postgresql+psycopg://docbot:docbot@localhost:5433/docbot"
    redis_url: str = "redis://localhost:6380/0"
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_expire_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:3000"

    llm_provider: str = "anthropic"  # anthropic | groq
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-5-5"
    llm_effort: str = "low"
    # Server-side refusal fallback (beta): reroutes a declined request to another model in the same call.
    llm_fallbacks: bool = True
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"

    embedding_provider: str = "voyage"  # voyage | hash
    voyage_api_key: str | None = None
    voyage_model: str = "voyage-3.5"

    storage_dir: Path = API_ROOT / "storage"

    chunk_tokens: int = 400
    chunk_overlap: int = 60
    retrieve_k: int = 20
    context_k: int = 6
    # Below this vector similarity, a question is flagged as likely not covered by the docs.
    low_confidence_score: float = 0.35

    widget_rate_limit_per_min: int = 20
    login_rate_limit_per_min: int = 10
    crawl_max_pages: int = 25

    @model_validator(mode="after")
    def require_strong_secret_in_production(self) -> "Settings":
        # Anyone who knows or guesses the secret can sign login tokens for any account.
        if self.app_env == "production" and (
            self.jwt_secret == DEFAULT_JWT_SECRET or len(self.jwt_secret) < MIN_JWT_SECRET_LENGTH
        ):
            raise ValueError(
                f"JWT_SECRET must be a random string of at least {MIN_JWT_SECRET_LENGTH} characters in production"
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
