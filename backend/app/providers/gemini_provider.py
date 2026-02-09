from __future__ import annotations

import logging

from app.core.config import get_settings
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        self._settings = get_settings()
        api_key = self._settings.gemini_api_key
        if not api_key:
            raise ValueError(
                "Gemini API key is required. Set AI_TC_GEN_GEMINI_API_KEY in .env."
            )
        from google import genai
        self._client = genai.Client(api_key=api_key)

    async def generate_test_cases(self, prompt: str, **kwargs: object) -> str:
        model_id = (
            kwargs.get("model_id")
            if isinstance(kwargs.get("model_id"), str) and kwargs.get("model_id")
            else self._settings.gemini_model
        )
        max_output_tokens = 16384
        config = {
            "temperature": 0.3,
            "max_output_tokens": max_output_tokens,
            "response_mime_type": "application/json",
        }
        response = await self._client.aio.models.generate_content(
            model=model_id,
            contents=prompt,
            config=config,
        )
        if not response or not response.text:
            return ""
        return response.text
