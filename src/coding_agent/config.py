from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str
    gemini_api_key: str
    openrouter_api_key: str | None = None

    qdrant_url: str
    qdrant_api_key: str

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    coding_agent_max_iterations: int = Field(default=4, ge=1, le=20)
    coding_agent_task_timeout_sec: int = Field(default=600, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
