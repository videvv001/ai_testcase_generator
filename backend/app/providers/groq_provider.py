from __future__ import annotations

import logging
from typing import Optional

from app.core.config import get_settings
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    """LLM provider that calls the Groq API (groq SDK)."""

    def __init__(self) -> None:
        self._settings = get_settings()
        api_key = self._settings.groq_api_key
        if not api_key:
            raise ValueError(
                "Groq API key is required when using Groq provider. "
                "Set AI_TC_GEN_GROQ_API_KEY in .env."
            )
        from groq import AsyncGroq
        self._client = AsyncGroq(api_key=api_key)

    async def generate_test_cases(self, prompt: str, **kwargs: object) -> str:
        model_id = (
            kwargs.get("model_id")
            if isinstance(kwargs.get("model_id"), str) and kwargs.get("model_id")
            else self._settings.groq_model
        )
        max_tokens = 16384
        logger.info("Groq request: model=%s max_tokens=%s", model_id, max_tokens)
        response = await self._client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content if response.choices else None
        if content is None:
            return ""
        return content
