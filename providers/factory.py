from __future__ import annotations

from core.config import get_settings
from providers.base import LLMProvider
from providers.ollama_provider import OllamaProvider
from providers.openai_provider import OpenAIProvider


def get_provider(provider_name: str | None = None) -> LLMProvider:
    """
    Return the LLM provider for the given name.

    Args:
        provider_name: "ollama", "openai", or None to use default from config.

    Returns:
        An LLMProvider implementation.

    Raises:
        ValueError: If provider_name is not supported or config is invalid.
    """
    settings = get_settings()
    name = (provider_name or settings.default_llm_provider).strip().lower()

    if name == "ollama":
        return OllamaProvider()
    if name == "openai":
        return OpenAIProvider()

    raise ValueError(
        f"Unsupported LLM provider: {provider_name!r}. "
        "Use 'ollama' or 'openai'."
    )
