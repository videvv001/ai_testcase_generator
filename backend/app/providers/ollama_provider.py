from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

import httpx

from app.core.config import get_settings
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """LLM provider that calls a local Ollama HTTP API."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._settings = get_settings()
        self._client = client or httpx.AsyncClient(
            base_url=self._settings.ollama_base_url,
            timeout=httpx.Timeout(
                connect=10.0,
                read=float(self._settings.ollama_timeout_seconds),
                write=10.0,
                pool=10.0,
            ),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def generate_test_cases(self, prompt: str, **kwargs: object) -> str:
        max_retries = 3
        backoff_base_seconds = 1
        model_id = kwargs.get("model_id") if isinstance(kwargs.get("model_id"), str) else None
        model_name = model_id if model_id else self._settings.ollama_model
        payload: Dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 16000},
        }
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    "Requesting test case generation from Ollama",
                    extra={"model": model_name, "attempt": attempt, "max_retries": max_retries},
                )
                response = await self._client.post(
                    "/api/generate",
                    json=payload,
                    timeout=self._settings.ollama_timeout_seconds,
                )
                response.raise_for_status()
                data: Dict[str, Any] = response.json()
                raw_output = data.get("response")
                if isinstance(raw_output, str):
                    return raw_output
                return response.text
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_error = exc
                logger.warning(
                    "Ollama request failed",
                    extra={"attempt": attempt, "max_retries": max_retries, "error": str(exc)},
                )
                if attempt >= max_retries:
                    break
                await asyncio.sleep(backoff_base_seconds * (2 ** (attempt - 1)))
        assert last_error is not None
        raise last_error
