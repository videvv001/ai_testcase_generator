from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.
    """

    # Core app settings
    app_name: str = Field(default="ai_testcase_generator")
    environment: str = Field(default="development")  # development | staging | production
    debug: bool = Field(default=False)

    # HTTP server
    api_prefix: str = Field(default="/api")

    # Observability
    log_level: str = Field(default="INFO")

    # LLM provider selection ("ollama" | "openai")
    default_llm_provider: str = Field(
        default="ollama",
        description="Default LLM provider for test case generation.",
    )

    # Ollama
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for local Ollama HTTP API.",
    )
    ollama_model: str = Field(
        default="llama3.2:3b",
        description="Ollama model name for test generation.",
    )
    ollama_timeout_seconds: int = Field(default=600)

    # OpenAI (when provider is openai)
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key. Required when using OpenAI provider.",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model: gpt-4o-mini or gpt-4o.",
    )
    openai_timeout_seconds: int = Field(default=120)

    # Security (placeholder for future auth)
    api_key_header_name: Optional[str] = Field(default=None)

    model_config = SettingsConfigDict(
        env_prefix="AI_TC_GEN_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached settings instance for use as a dependency.
    """
    return Settings()
