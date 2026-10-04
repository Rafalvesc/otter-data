from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_host: str = "127.0.0.1"
    database_port: int = Field(default=55432, ge=1, le=65535)
    database_name: str = "datapilot"
    # Read-only account of the PostgreSQL sample (Docker). Without it, the sample base is the
    # embedded DuckDB copy (backend.sample.embedded), which is what the installed app uses.
    analytics_password: SecretStr | None = None
    query_timeout_seconds: int = Field(default=10, ge=1, le=10)
    max_rows: int = Field(default=10000, ge=1, le=10000)
    max_result_bytes: int = Field(default=1000000, ge=128, le=1000000)
    # "demo" answers the reference questions with scripted output and no model (tests, offline).
    llm_provider: Literal["ollama", "demo"] = "ollama"
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434", pattern=r"^https?://[^\s/?#]+/?$", max_length=200
    )
    ollama_model: str = Field(default="gemma4:31b-cloud", min_length=1, max_length=100)
    # Extra models offered in the picker (comma-separated). Installed Ollama models are listed
    # automatically; cloud models work without `ollama pull`, so they can be offered here.
    ollama_models: str = Field(default="", max_length=1000)
    # Local models run on this machine's CPU/GPU and are much slower than cloud models.
    local_llm_timeout_seconds: int = Field(default=120, ge=5, le=600)
    local_request_timeout_seconds: int = Field(default=480, ge=10, le=1800)
    # Context window asked of local models. Ollama's own default (4096 tokens) silently
    # drops the start of longer prompts, i.e. the instructions; prompts here reach 3-6k.
    local_context_tokens: int = Field(default=16384, ge=4096, le=131072)
    llm_timeout_seconds: int = Field(default=20, ge=1, le=30)
    request_timeout_seconds: int = Field(default=60, ge=1, le=120)
    max_llm_calls: int = Field(default=4, ge=1, le=4)
    # Who built this Otter Data instance, so the assistant can say it instead of guessing.
    otter_author: str = Field(default="", max_length=120)
    # Earlier exchanges of the same conversation sent to the model as context.
    history_turns: int = Field(default=6, ge=0, le=8)
    max_concurrent_requests: int = Field(default=4, ge=1, le=4)
    exploration_enabled: bool = True
    # Sends at most narrative_max_rows result rows to the model to write a natural-language answer.
    narrative_enabled: bool = True
    narrative_max_rows: int = Field(default=50, ge=1, le=200)
    # Connected sources: configs and imported CSVs (passwords stay in the OS credential vault).
    data_dir: str | None = None
    csv_max_mb: int = Field(default=50, ge=1, le=500)

    @property
    def llm_model(self) -> str | None:
        # The local Ollama daemon holds the ollama.com sign-in; the app needs no API key.
        return self.ollama_model if self.llm_provider == "ollama" else None

    @property
    def embedded_sample(self) -> bool:
        return self.analytics_password is None

    @property
    def analytics_url(self) -> URL:
        if self.analytics_password is None:
            raise RuntimeError(
                "ANALYTICS_PASSWORD não configurada: a base de exemplo é a embutida."
            )
        # Username is deliberately not configurable to an administrator account.
        return URL.create(
            "postgresql+psycopg",
            username="analytics_agent",
            password=self.analytics_password.get_secret_value(),
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
