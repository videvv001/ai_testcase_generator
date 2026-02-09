from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (parent of backend/) for .env loading when running from backend/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


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

    # Gemini (when provider is gemini)
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Gemini API key. Required when using Gemini provider. Set AI_TC_GEN_GEMINI_API_KEY in .env.",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model name for test generation.",
    )
    gemini_timeout_seconds: int = Field(default=120)

    # Groq (when provider is groq)
    groq_api_key: Optional[str] = Field(
        default=None,
        description="Groq API key. Required when using Groq provider. Set AI_TC_GEN_GROQ_API_KEY in .env.",
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model name for test generation.",
    )
    groq_timeout_seconds: int = Field(default=120)

    # Security (placeholder for future auth)
    api_key_header_name: Optional[str] = Field(default=None)

    model_config = SettingsConfigDict(
        env_prefix="AI_TC_GEN_",
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached settings instance for use as a dependency.
    """
    return Settings()
