from __future__ import annotations

import logging
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.providers.base import LLMProvider
from app.utils.token_allocation import calculate_dynamic_max_tokens


logger = logging.getLogger(__name__)

# UI profile → OpenAI model: Fast = gpt-4o-mini, Smart = gpt-4o. Private uses Ollama.
OPENAI_MODEL_BY_PROFILE: dict[str, str] = {
    "fast": "gpt-4o-mini",
    "smart": "gpt-4o",
}


def _resolve_openai_model(model_profile: str | None, fallback: str) -> str:
    """Resolve UI model_profile to OpenAI model name. Private/unknown use fallback from config."""
    if not model_profile:
        return fallback
    return OPENAI_MODEL_BY_PROFILE.get(model_profile.strip().lower(), fallback)


class OpenAIProvider(LLMProvider):
    """
    LLM provider that calls the OpenAI Chat Completions API.

    Supports gpt-4o-mini and gpt-4o. Model is configured via settings.
    Uses dynamic max_tokens based on prompt size, coverage level, and model context window.
    """

    def __init__(self, client: Optional[AsyncOpenAI] = None) -> None:
        self._settings = get_settings()
        if client is not None:
            self._client = client
        else:
            api_key = self._settings.openai_api_key
            if not api_key:
                raise ValueError(
                    "OpenAI API key is required when using OpenAI provider. "
                    "Set AI_TC_GEN_OPENAI_API_KEY in environment or .env."
                )
            self._client = AsyncOpenAI(api_key=api_key)

    async def generate_test_cases(self, prompt: str, **kwargs: object) -> str:
        coverage_level: str = (
            kwargs.get("coverage_level")
            if isinstance(kwargs.get("coverage_level"), str)
            else "medium"
        )
        model_id = kwargs.get("model_id") if isinstance(kwargs.get("model_id"), str) else None
        model_profile = kwargs.get("model_profile") if isinstance(kwargs.get("model_profile"), str) else None
        if model_id and model_id in ("gpt-4o-mini", "gpt-4o"):
            model_name = model_id
        else:
            model_name = _resolve_openai_model(model_profile, self._settings.openai_model)
        max_tokens = calculate_dynamic_max_tokens(
            prompt=prompt,
            coverage_level=coverage_level,
            model_name=model_name,
        )

        logger.info(
            "OpenAI request: model=%s profile=%s max_tokens=%s",
            model_name,
            model_profile or "(fallback)",
            max_tokens,
        )

        response = await self._client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=max_tokens,
        )

        # Confirm which model was actually used (OpenAI may echo or normalize the name).
        response_model = getattr(response, "model", None) or getattr(response, "model_name", None)
        logger.info(
            "OpenAI response: model_used=%s",
            response_model or model_name,
        )

        content = response.choices[0].message.content
        if content is None:
            return ""
        return content
