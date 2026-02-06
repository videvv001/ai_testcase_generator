from __future__ import annotations

import logging
from typing import Optional

from openai import AsyncOpenAI

from core.config import get_settings
from providers.base import LLMProvider


logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    LLM provider that calls the OpenAI Chat Completions API.

    Supports gpt-4o-mini and gpt-4o. Model is configured via settings.
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

    async def generate_test_cases(self, prompt: str) -> str:
        logger.info(
            "Requesting test case generation from OpenAI",
            extra={"model": self._settings.openai_model},
        )

        response = await self._client.chat.completions.create(
            model=self._settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        content = response.choices[0].message.content
        if content is None:
            return ""
        return content
